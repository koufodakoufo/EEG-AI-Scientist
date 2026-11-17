"""Prospective resource delivery and clean continuation; no model or EEG runs."""
import hashlib
import json

import pytest

from eegfm.agent import provider, provider_export, provider_trace
from eegfm.agent.controller import ResearchController, ResearchDriver
from eegfm.evaluation.bundle import canonical_bytes, create_public_bundle, digest_file
from test_agent_provider import setup_provider, open_session, call, complete_trace, Evaluator


TEXT_PATHS = ("API_README.md", "INTERFACE.md", "PUBLIC_RESULT_SCHEMA.md", "TASK.md",
              "eeg_api.py", "resources/CACHE_SCHEMA.json", "resources/PAPER_TASK.json")


def bundled_provider(tmp_path, setup_provider, *, changed=None, missing=None):
    controller, old, enrollment = setup_provider
    source = tmp_path / "bundle-source"
    source.mkdir()
    contents = {name: (f"Exact {name}\r\nUTF-8: \u03b1\n" * 130).encode() for name in TEXT_PATHS}
    contents.update(changed or {})
    for name, raw in contents.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    (source / "train.npz").write_bytes(b"PRIVATE-ARRAY-CONTENT-NOT-TEXT")
    (source / "private-reference.json").write_text('{"answer":"PRIVATE-REFERENCE"}')
    public = tmp_path / "bundle-public"
    names = [name for name in TEXT_PATHS if name != missing] + ["train.npz"]
    create_public_bundle(source, public, names, task_id="synthetic", tier="synthetic_mechanism")
    controller = ResearchController(trusted_root=tmp_path / 'bundle-control', case_root=old.case,
        episode_id='episode', run_id='run', public_manifest_sha256=digest_file(public / 'PUBLIC_MANIFEST.json'),
        split_manifest_sha256='a' * 64, evaluator=Evaluator())
    identity = {**enrollment, "public_resource_delivery": "manifest_text_bundle_v1"}
    box = provider.ProviderMailbox(root=controller.run / "provider", case_root=old.case,
                                   public_root=public, enrollment=identity)
    return controller, box, contents


def test_bundle_delivered_once_after_admission_with_exact_manifest_bytes(tmp_path, setup_provider):
    _, box, contents = bundled_provider(tmp_path, setup_provider)
    open_session(box, register=False)
    assert call(box, "task", request_id="task")["status"] == "awaiting_context_admission"
    assert not box.session("session-01")["task_read"]
    box.register_context("session-01", context_id="context", trace_path=box.root / "synthetic-native-prefix.jsonl")
    result = call(box, "request_status", {"request_id": "task"})["result"]["response"]
    bundle = result["result"]["public_resource_bundle"]
    assert bundle["schema_version"] == "manifest_text_bundle_v1"
    assert bundle["public_manifest_sha256"] == digest_file(box.public / "PUBLIC_MANIFEST.json")
    assert bundle["bytes"] == sum(map(len, contents.values()))
    assert {row["path"] for row in bundle["files"]} == set(TEXT_PATHS)
    for row in bundle["files"]:
        assert row["text"].encode("utf-8") == contents[row["path"]]
        assert row["bytes"] == len(contents[row["path"]])
        assert row["sha256"] == hashlib.sha256(contents[row["path"]]).hexdigest()
    assert b"PRIVATE-ARRAY-CONTENT" not in canonical_bytes(result)
    assert b"PRIVATE-REFERENCE" not in canonical_bytes(result)
    assert call(box, "task", request_id="task") == result
    assert call(box, "task")["status"] == "rejected"


@pytest.mark.parametrize("case", ["missing", "non_utf8", "oversize", "drift"])
def test_bundle_rejects_missing_invalid_oversized_or_changed_text(tmp_path, setup_provider, case):
    changes = {"TASK.md": b"\xff"} if case == "non_utf8" else {"TASK.md": b"x" * 65537} if case == "oversize" else None
    _, box, _ = bundled_provider(tmp_path, setup_provider, changed=changes,
                                 missing="eeg_api.py" if case == "missing" else None)
    open_session(box)
    if case == "drift":
        (box.public / "TASK.md").write_bytes(b"changed")
        with pytest.raises(ValueError):
            call(box, "task")
    else:
        assert call(box, "task")["status"] == "rejected"


def test_bundle_policy_and_larger_output_templates_are_exactly_bound(tmp_path, setup_provider):
    _, box, _ = bundled_provider(tmp_path, setup_provider)
    request = {"request_id": "task", "operation": "task", "payload": {}}
    template = provider.call_template(box.identity, "session-01", json.dumps(request))
    poll = provider.poll_template(345, identity=box.identity)
    pragma = '// @exec: {"max_output_tokens":24000}\n'
    assert template.startswith(pragma) and poll.startswith(pragma)
    assert "max_output_tokens:20000" in template and "max_output_tokens:20000" in poll
    assert provider_trace.parse_tool(template, box.identity, "session-01") == ("call", request)
    assert provider_trace.parse_tool(poll, box.identity, "session-01") == ("poll", 345)
    for bad in (template.replace("20000", "16000"), poll.replace("20000", "9000"), poll.replace("20000", "20001"),
                template.removeprefix(pragma), poll.replace('24000', '24001')):
        with pytest.raises(ValueError):
            provider_trace.parse_tool(bad, box.identity, "session-01")
    old = {key: value for key, value in setup_provider[2].items()}
    assert "max_output_tokens:9000" in provider.call_template(old, "session-01", json.dumps(request))
    assert provider_export.audit_profile(old) != provider_export.audit_profile(box.identity)
    with pytest.raises(ValueError, match='enrollment drift'):
        provider.ProviderMailbox(root=box.root, case_root=box.case, public_root=box.public, enrollment=old)


def test_bundled_wait_template_keeps_pragma_first_and_literal_wait_after_it(tmp_path, setup_provider):
    _, box, _ = bundled_provider(tmp_path, setup_provider)
    request = {'request_id': 'task-status-01', 'operation': 'request_status', 'payload': {'request_id': 'task'}}
    code = provider.call_template(box.identity, 'session-01', json.dumps(request), wait=True)
    assert code.splitlines()[0] == '// @exec: {"max_output_tokens":24000}'
    assert code.splitlines()[1].startswith(provider.WAIT_STATUS_PREFIX)
    assert provider_trace.parse_tool(code, box.identity, 'session-01') == ('call', request)


def test_complete_bundle_delivery_audit_rejects_tool_output_truncation(tmp_path, setup_provider):
    _, box, _ = bundled_provider(tmp_path, setup_provider)
    open_session(box)
    call(box, 'task')
    call(box, 'seal_session', {'requests': []})
    path = complete_trace(box)
    state = box.session('session-01')
    assert provider_trace.audit_native_context(path, box.identity, state, box.deliveries('session-01'))['valid']
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    output = next(row['payload'] for row in rows if row['payload'].get('type') == 'custom_tool_call_output')
    envelope = json.loads(output['output'][1]['text'])
    envelope['output'] = envelope['output'][:-30]
    output['output'][1]['text'] = json.dumps(envelope)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert not provider_trace.audit_native_context(path, box.identity, state, box.deliveries('session-01'))['valid']


def test_inline_checkpoint_is_audited_then_copied_into_fresh_session(tmp_path, setup_provider):
    from eegfm.agent.driver import Driver
    controller, box, _ = bundled_provider(tmp_path, setup_provider)
    driver = ResearchDriver(controller, launch=lambda _: None, session_provider=provider.PROVIDER,
                            provider_model=box.identity['model'])
    continued = []
    class ContinuationObserved(Exception):
        pass
    def launch(projection):
        identifier = projection['provider_session']['reservation_id']
        if identifier != 'session-01':
            continued.append(box.publish(identifier, projection, timeout_seconds=240))
            raise ContinuationObserved  # Stop before a second model would be dispatched.
        open_session(box, projection=projection)
        task = call(box, "task")["result"]
        assert task["operations"]["seal_session"] == {"requests": []}
        assert "brief only" in task["instructions"]
        text = "Work in progress; no fitted scientific result.\n"
        written = call(box, "write_chunk", {"path": "notes.md", "offset": 0, "text": text})
        call(box, "seal_file", {"path": "notes.md", "sha256": written["result"]["sha256"]})
        assert call(box, "seal_session", {"requests": []})["status"] == "ok"
        return box.accept_trace("session-01", complete_trace(box))
    driver.launch = launch
    # Exercise the real shared loop's stall accounting. The Linux-only lease is
    # outside this portable test; no process or actual model is started here.
    with pytest.raises(ContinuationObserved):
        Driver.loop(driver)
    records = [json.loads(line) for line in (controller.run / 'sessions.jsonl').read_text().splitlines()]
    assert records[0]['ok'] and records[0]['error'] is None
    assert records[0]['status'] == 'finished' and records[1]['status'] == 'reserved'
    assert controller.projection()['state']['status'] == 'brief'
    next_session, = continued
    next_id = next_session['session_id']
    assert next_session["agent_path"] != box.session("session-01")["agent_path"]
    assert box.session(next_id)["registered_context"] is None
    original = box.session(next_id)["original_manifest"]
    assert original == provider.tree_manifest(controller.case / "output")
    assert (box._pending_root(next_id) / "notes.md").read_bytes() == (controller.case / "output/notes.md").read_bytes()
    assert len((controller.run / 'sessions.jsonl').read_text().splitlines()) == 2

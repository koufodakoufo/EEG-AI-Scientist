"""Offline tests for the Flash overnight stack.

No real API key or network call is used here.  Real connectivity is checked
separately by the capability command and reported as such.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from eeg_scientist.credentials import CredentialError, load_deepseek_key
from eeg_scientist.dataset_io import (
    DatasetFormatError,
    check_feature_table,
    load_feature_table,
    write_artificial_fixture,
)
from eeg_scientist.deepseek_api import (
    DeepSeekChatResult,
    DeepSeekClient,
    DeepSeekError,
    DeepSeekToolCall,
    DeepSeekUsage,
    FetchResponse,
    SearchItem,
    SearchResponse,
)
from eeg_scientist.diagnostic import evaluate_regression
from eeg_scientist.evidence import EvidenceError, EvidenceStore, estimate_injection_fraction
from eeg_scientist.ledger import BudgetExceeded, BudgetLedger
from eeg_scientist.research import ResearchConfig, ResearchError, ResearchRunner


def _ledger(tmp_path: Path) -> BudgetLedger:
    return BudgetLedger(tmp_path / "budget.json", run_id="test_run", cap_cny=20.0, wrap_up_reserve_cny=2.0)


def test_credentials_accept_keyed_file_and_reject_bare_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good = tmp_path / "deepseek.env"
    good.write_text("DEEPSEEK_API_KEY=sk-test-0123456789abcdef\n", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    key, report = load_deepseek_key(good)
    assert key.startswith("sk-test")
    assert report.key_present and report.key_length == len(key)
    assert "sk-test" not in json.dumps(report.public_dict())

    bare = tmp_path / "bare.env"
    bare.write_text("sk-test-0123456789abcdef\n", encoding="utf-8")
    with pytest.raises(CredentialError):
        load_deepseek_key(bare)

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-other-0123456789abcdef")
    _key, conflict = load_deepseek_key(good)
    assert conflict.environment_conflict is True


def test_ledger_settles_and_keeps_unknown(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    reservation = ledger.reserve_model("hello", 1000)
    assert ledger.state.model_attempts == 1
    assert ledger.state.reserved_cny > 0
    ledger.settle_model(reservation.reservation_id, prompt_tokens=10, completion_tokens=5)
    assert ledger.state.reserved_cny == pytest.approx(0.0)
    assert ledger.state.spent_cny > 0
    assert ledger.state.input_tokens == 10
    assert ledger.state.output_tokens == 5

    second = ledger.reserve_model("again", 1000)
    ledger.mark_unknown(second.reservation_id, "timeout")
    assert ledger.state.unknown_cny > 0
    assert ledger.state.model_attempts == 2


def test_ledger_rejects_new_spend_above_cap(tmp_path: Path) -> None:
    ledger = BudgetLedger(tmp_path / "budget.json", run_id="test_run", cap_cny=0.001, wrap_up_reserve_cny=0.0)
    with pytest.raises(BudgetExceeded):
        ledger.reserve_model("x" * 10000, 16384)


def test_chat_preserves_reasoning_and_tool_call_fields(tmp_path: Path) -> None:
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen.append(body)
        if len(seen) == 1:
            return httpx.Response(
                200,
                json={
                    "id": "resp_1",
                    "model": "deepseek-flash",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "reasoning_content": "I should call the echo tool.",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {"name": "echo_probe", "arguments": "{\"text\":\"ping\"}"},
                                    }
                                ],
                            },
                            "finish_reason": "tool_calls",
                        }
                    ],
                    "usage": {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "resp_2",
                "model": "deepseek-flash",
                "choices": [{"message": {"role": "assistant", "content": "ping"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 2, "total_tokens": 42},
            },
        )

    ledger = _ledger(tmp_path)
    client = DeepSeekClient(api_key="sk-test", ledger=ledger, transport=httpx.MockTransport(handler))
    first = client.chat([{"role": "user", "content": "call echo"}], tools=[{"type": "function", "function": {"name": "echo_probe", "parameters": {"type": "object"}}}])
    assert first.tool_calls[0].name == "echo_probe"
    messages: list[dict[str, object]] = [
        {"role": "user", "content": "call echo"},
        {
            "role": "assistant",
            "content": first.content,
            "reasoning_content": first.reasoning_content,
            "tool_calls": [
                {"id": first.tool_calls[0].id, "type": "function", "function": {"name": first.tool_calls[0].name, "arguments": first.tool_calls[0].arguments}}
            ],
        },
        {"role": "tool", "tool_call_id": first.tool_calls[0].id, "content": "ping"},
    ]
    second = client.chat(messages, tools=[{"type": "function", "function": {"name": "echo_probe", "parameters": {"type": "object"}}}])
    assert second.content == "ping"
    second_request = seen[1]
    wire_messages = second_request["messages"]
    assert wire_messages[1]["reasoning_content"] == "I should call the echo tool."
    assert wire_messages[2]["tool_call_id"] == "call_1"
    assert second_request["max_tokens"] == 16384
    assert second_request["thinking"] == {"type": "enabled"}


def test_evidence_read_records_injection(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    record = store.add_text(url="https://example.org/x", title="X", text="abcdefghij" * 10)
    sliced = store.read(record.evidence_id, start_char=5, max_chars=20)
    assert sliced.text == ("abcdefghij" * 10)[5:25]
    assert record.evidence_id in store.injected_ids()
    with pytest.raises(EvidenceError):
        store.read("../../etc/passwd")
    with pytest.raises(EvidenceError):
        store.read(record.evidence_id, start_char=0, max_chars=99999)
    assert (tmp_path / "injections.jsonl").exists()


def test_coverage_uses_union_not_sum_of_overlapping_reads(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    record = store.add_text(url="https://example.org/long", title="Long", text="a" * 100)
    store.read(record.evidence_id, start_char=0, max_chars=20)
    store.read(record.evidence_id, start_char=10, max_chars=20)
    store.read(record.evidence_id, start_char=15, max_chars=10)

    coverage = estimate_injection_fraction(store)
    row = next(item for item in coverage["sources"] if item["evidence_id"] == record.evidence_id)
    assert row["read_chars"] == 30
    assert row["fraction_read"] == pytest.approx(0.3)


def test_usage_missing_is_unknown_not_zero_cost(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "resp_no_usage",
                "model": "deepseek-flash",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            },
        )

    ledger = _ledger(tmp_path)
    client = DeepSeekClient(api_key="sk-test", ledger=ledger, transport=httpx.MockTransport(handler))
    with pytest.raises(DeepSeekError, match="usage"):
        client.chat([{"role": "user", "content": "hello"}])
    assert ledger.state.spent_cny == pytest.approx(0.0)
    assert ledger.state.unknown_cny > 0
    assert ledger.state.reserved_cny == pytest.approx(0.0)
    assert ledger.state.pending == {}


def test_usage_invalid_is_unknown_not_zero_cost(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "resp_bad_usage",
                "model": "deepseek-flash",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": "not-a-number", "completion_tokens": 2},
            },
        )

    ledger = _ledger(tmp_path)
    client = DeepSeekClient(api_key="sk-test", ledger=ledger, transport=httpx.MockTransport(handler))
    with pytest.raises(DeepSeekError, match="usage"):
        client.chat([{"role": "user", "content": "hello"}])
    assert ledger.state.spent_cny == pytest.approx(0.0)
    assert ledger.state.unknown_cny > 0
    assert ledger.state.pending == {}


def test_dataset_fixture_roundtrip(tmp_path: Path) -> None:
    path = write_artificial_fixture(tmp_path / "fixture.csv")
    dataset = load_feature_table(path)
    assert len(dataset.sample_ids) == 4 * 2 * 8 * 4
    assert len(set(dataset.subject_ids)) == 4
    summary = check_feature_table(path)
    assert summary["n_subjects"] == 4
    assert summary["fixture_only"] is True
    assert summary["label_domain"] == "binary_-1_1"
    assert summary["split_levels_supported"] == ["window", "trial", "subject"]
    assert summary["session_split_supported"] is False
    for audit in summary["audits"].values():
        assert audit["invalid_reason"] is None


@pytest.mark.parametrize("label", ["1.5", "1.0", "-1.0", "1e0", ""])
def test_csv_decimal_or_non_integer_label_is_rejected(tmp_path: Path, label: str) -> None:
    path = tmp_path / "bad_label.csv"
    path.write_text(
        "sample_id,subject_id,session_id,trial_id,label,f0\n"
        f"s1,sub-01,sub-01_ses-01,t1,{label},0.5\n",
        encoding="utf-8",
    )
    with pytest.raises(DatasetFormatError, match="integer"):
        load_feature_table(path)


def test_csv_integer_label_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "good_label.csv"
    path.write_text(
        "sample_id,subject_id,session_id,trial_id,label,f0\n"
        "s1,sub-01,sub-01_ses-01,t1,-1,0.5\n",
        encoding="utf-8",
    )
    dataset = load_feature_table(path)
    assert dataset.y.tolist() == [-1]


def test_regression_rule_checks_detect_collapse_claim() -> None:
    good = (
        "原标签 window 99.3%，随机标签后 99.2%，只变化 0.1 个百分点，几乎没有变化。"
        "trial 切分原标签 49.6%，本来已接近机会水平 50%；随机化后 50.8%，变化 1.2 个百分点。"
        "因此不能说随机化使 trial 性能从高水平降到机会水平。"
        "window 切分允许同一试次的不同窗口同时出现在训练和测试侧，所以不能据此认为任务语义泛化成立，"
        "也不足以排除窗口级泄漏或会话/被试因素。"
    )
    evaluation = evaluate_regression(good)
    assert evaluation["n_pass"] >= 5
    bad = good + "也可以说随机化导致 trial 性能从 99% 下降到 50% 的机会水平。"
    bad_eval = evaluate_regression(bad)
    reject = [item for item in bad_eval["checks"] if item["check"] == "rejects_trial_collapse_claim"][0]
    assert reject["pass"] is False


class _FakeClient:
    model_name = "deepseek-flash"

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[str] = []
        self.finished = False
        self.evidence_id = "ev_" + hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]

    def chat(self, messages, *, tools=None, max_tokens=16384, json_mode=False, stage=""):  # type: ignore[no-untyped-def]
        self.calls.append(stage)
        if self.finished:
            raise AssertionError("completed runner must not call the model again")
        if not any(message.get("role") == "tool" and "search_id" in str(message.get("content", "")) for message in messages):
            return DeepSeekChatResult(
                content="",
                reasoning_content="search first",
                tool_calls=[DeepSeekToolCall(id="c1", name="search_sources", arguments=json.dumps({"query": "eeg decoding"}))],
                finish_reason="tool_calls",
                requested_model="deepseek-flash",
                returned_model="deepseek-flash",
                usage=DeepSeekUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
            )
        if not any(message.get("role") == "tool" and "evidence_id" in str(message.get("content", "")) for message in messages):
            return DeepSeekChatResult(
                content="",
                reasoning_content="fetch",
                tool_calls=[DeepSeekToolCall(id="c2", name="fetch_source", arguments=json.dumps({"url": "https://example.org/paper"}))],
                finish_reason="tool_calls",
                requested_model="deepseek-flash",
                returned_model="deepseek-flash",
                usage=DeepSeekUsage(prompt_tokens=120, completion_tokens=20, total_tokens=140),
            )
        if not any(
            message.get("role") == "tool" and "character range" in str(message.get("content", ""))
            for message in messages
        ):
            return DeepSeekChatResult(
                content="",
                reasoning_content="read",
                tool_calls=[DeepSeekToolCall(id="c3", name="read_evidence", arguments=json.dumps({"evidence_id": self.evidence_id, "max_chars": 100}))],
                finish_reason="tool_calls",
                requested_model="deepseek-flash",
                returned_model="deepseek-flash",
                usage=DeepSeekUsage(prompt_tokens=140, completion_tokens=20, total_tokens=160),
            )
        self.finished = True
        return DeepSeekChatResult(
            content="",
            reasoning_content="finish",
            tool_calls=[
                DeepSeekToolCall(
                    id="c4",
                    name="finish_study",
                    arguments=json.dumps(
                        {
                            "answer": self.content + f"\n\nCites [{self.evidence_id}].",
                            "evidence_ids": [self.evidence_id],
                            "unresolved": ["test gap"],
                        }
                    ),
                )
            ],
            finish_reason="tool_calls",
            requested_model="deepseek-flash",
            returned_model="deepseek-flash",
            usage=DeepSeekUsage(prompt_tokens=160, completion_tokens=20, total_tokens=180),
        )

    def search(self, query, *, count=8, need_content=False):  # type: ignore[no-untyped-def]
        return SearchResponse(
            query=query,
            results=[SearchItem(result_id="sr_01", title="Paper", url="https://example.org/paper", summary="lead")],
        )

    def fetch(self, url):  # type: ignore[no-untyped-def]
        return FetchResponse(url=url, title="Paper", content=self.content)


def test_research_runner_completes_and_resumes(tmp_path: Path) -> None:
    content = "This synthetic test document says something long enough to read and cite. " * 10
    client = _FakeClient(content)
    ledger = _ledger(tmp_path)
    config = ResearchConfig(
        run_id="test_research",
        run_dir=str(tmp_path / "research"),
        question="test question",
        deadline="2099-01-01T00:00:00+00:00",
        stop_new_at="2099-01-01T00:00:00+00:00",
        allowed_experiments=["fixture_split_check"],
    )
    runner = ResearchRunner(config, client=client, ledger=ledger)
    summary = runner.run()
    assert summary.phase == "completed"
    final = json.loads((tmp_path / "research" / "final.json").read_text(encoding="utf-8"))
    assert final["evidence_ids"] == [client.evidence_id]
    assert final["inline_evidence_ids"] == [client.evidence_id]
    assert (tmp_path / "research" / "evidence" / "sources" / f"{client.evidence_id}.json").exists()
    messages = json.loads((tmp_path / "research" / "messages.json").read_text(encoding="utf-8"))
    assistant = [message for message in messages if message.get("role") == "assistant"]
    assert all("reasoning_content" in message for message in assistant)
    calls_before = len(client.calls)
    again = ResearchRunner(config, client=client, ledger=ledger).run()
    assert again.phase == "completed"
    assert len(client.calls) == calls_before


def test_finish_study_requires_inline_and_listed_evidence_ids_to_match(tmp_path: Path) -> None:
    content = "A synthetic document used only for citation-consistency tests. " * 10
    client = _FakeClient(content)
    config = ResearchConfig(
        run_id="test_finish_citations",
        run_dir=str(tmp_path / "research"),
        question="test question",
        deadline="2099-01-01T00:00:00+00:00",
        stop_new_at="2099-01-01T00:00:00+00:00",
    )
    runner = ResearchRunner(config, client=client, ledger=_ledger(tmp_path))
    first = runner.evidence.add_text(url="https://example.org/a", title="A", text="first source " * 20)
    second = runner.evidence.add_text(url="https://example.org/b", title="B", text="second source " * 20)
    runner.evidence.read(first.evidence_id, max_chars=10)
    runner.evidence.read(second.evidence_id, max_chars=10)
    call = DeepSeekToolCall(id="finish_1", name="finish_study", arguments="{}")
    padding = "x" * 240

    listed_only = {
        "answer": f"Finding [{first.evidence_id}] {padding}",
        "evidence_ids": [first.evidence_id, second.evidence_id],
        "unresolved": [],
    }
    with pytest.raises(ResearchError, match="exactly the same evidence"):
        runner._tool_finish(listed_only, call)

    inline_only = {
        "answer": f"Finding [{first.evidence_id}] and [{second.evidence_id}] {padding}",
        "evidence_ids": [first.evidence_id],
        "unresolved": [],
    }
    with pytest.raises(ResearchError, match="exactly the same evidence"):
        runner._tool_finish(inline_only, call)

    matching = {
        "answer": f"Finding [{first.evidence_id}] {padding}",
        "evidence_ids": [first.evidence_id],
        "unresolved": [],
    }
    result = runner._tool_finish(matching, call)
    assert result["status"] == "completed"
    final = json.loads((tmp_path / "research" / "final.json").read_text(encoding="utf-8"))
    assert final["evidence_ids"] == [first.evidence_id]
    assert final["inline_evidence_ids"] == [first.evidence_id]

"""Real connectivity checks for the DeepSeek Flash route.

These are engineering checks, not research results.  Every call goes through the
same ledger and client as the research loop.  Failures are recorded; they are
never replaced by a mock success.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..deepseek_api import DeepSeekClient, DeepSeekError
from ..evidence import EvidenceStore
from ..storage import atomic_write_json, atomic_write_text, ensure_dir, utc_now

ECHO_TOOL: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "echo_probe",
        "description": "Return the supplied text unchanged. Used only for an engineering connectivity check.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to echo."}},
            "required": ["text"],
        },
    },
}


def _assistant_message(content: str, reasoning: str, tool_calls: list[dict[str, object]]) -> dict[str, object]:
    message: dict[str, object] = {"role": "assistant", "content": content, "reasoning_content": reasoning}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def run_capability_check(client: DeepSeekClient, *, run_dir: Path) -> dict[str, object]:
    target = ensure_dir(run_dir)
    started_at = utc_now()
    checks: list[dict[str, object]] = []

    def record(name: str, ok: bool, detail: dict[str, object]) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    # 1. Free model list.
    try:
        models = client.list_models()
        model_ids = [
            str(item.get("id"))
            for item in models.get("data", [])
            if isinstance(item, dict) and item.get("id")
        ] if isinstance(models.get("data"), list) else []
        record("list_models", "deepseek-flash" in model_ids, {"model_ids": model_ids, "http": 200})
    except DeepSeekError as error:
        record("list_models", False, {"error": str(error), "kind": error.kind})

    # 2. Tiny chat, JSON mode, thinking enabled.
    try:
        tiny = client.chat(
            [
                {"role": "system", "content": "Return only one JSON object: {\"ok\": true, \"route\": \"deepseek-flash\"}."},
                {"role": "user", "content": "Confirm the route."},
            ],
            tools=None,
            max_tokens=1024,
            json_mode=True,
            stage="capability_tiny",
        )
        parsed: object = None
        try:
            parsed = json.loads(tiny.content)
        except json.JSONDecodeError:
            parsed = None
        record(
            "chat_json_thinking",
            isinstance(parsed, dict) and bool(parsed.get("ok")),
            {
                "returned_model": tiny.returned_model,
                "finish_reason": tiny.finish_reason,
                "usage": tiny.usage.model_dump(mode="json"),
                "content_preview": tiny.content[:300],
                "reasoning_chars": len(tiny.reasoning_content),
                "request_id": tiny.request_id,
            },
        )
    except DeepSeekError as error:
        record("chat_json_thinking", False, {"error": str(error), "kind": error.kind, "status_code": error.status_code})

    # 3. Native tool cycle: model asks -> project executes -> model receives -> final text.
    messages: list[dict[str, object]] = [
        {
            "role": "user",
            "content": "Call echo_probe with text='ping'. After you receive the tool result, state the exact text that was returned.",
        }
    ]
    cycle_ok = False
    cycle_detail: dict[str, object] = {"turns": []}
    try:
        for turn in range(3):
            result = client.chat(messages, tools=[ECHO_TOOL], max_tokens=2048, json_mode=False, stage=f"capability_tool_{turn + 1}")
            turn_detail: dict[str, object] = {
                "turn": turn + 1,
                "finish_reason": result.finish_reason,
                "content": result.content[:300],
                "tool_calls": [{"id": item.id, "name": item.name, "arguments": item.arguments} for item in result.tool_calls],
                "reasoning_chars": len(result.reasoning_content),
            }
            messages.append(
                _assistant_message(
                    result.content,
                    result.reasoning_content,
                    [
                        {
                            "id": item.id,
                            "type": "function",
                            "function": {"name": item.name, "arguments": item.arguments},
                        }
                        for item in result.tool_calls
                    ],
                )
            )
            if not result.tool_calls:
                cycle_ok = "ping" in result.content.lower()
                turn_detail["final_text"] = result.content
                cycle_detail["turns"].append(turn_detail)  # type: ignore[union-attr]
                break
            for call in result.tool_calls:
                if call.name != "echo_probe":
                    tool_payload = {"status": "error", "error": f"unexpected tool {call.name}"}
                else:
                    try:
                        arguments = json.loads(call.arguments or "{}")
                        text = str(arguments.get("text", ""))
                        tool_payload = {"status": "ok", "text": text, "note": "engineering echo only"}
                    except json.JSONDecodeError:
                        tool_payload = {"status": "error", "error": "invalid arguments"}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(tool_payload, ensure_ascii=False),
                    }
                )
                turn_detail.setdefault("executed", []).append(tool_payload)  # type: ignore[union-attr]
            cycle_detail["turns"].append(turn_detail)  # type: ignore[union-attr]
        record("native_tool_cycle", cycle_ok, cycle_detail)
        client_side = {
            "messages": messages,
            "note": "The assistant tool-call message includes reasoning_content; the tool message includes tool_call_id.",
        }
        atomic_write_json(target / "tool_cycle.json", client_side)
    except DeepSeekError as error:
        record("native_tool_cycle", False, {"error": str(error), "kind": error.kind, "status_code": error.status_code})

    # 4. Search.
    search_url = ""
    try:
        search = client.search("EEG cross-subject decoding generalization trial-wise split", count=5, need_content=False)
        if search.results:
            search_url = search.results[0].url
        atomic_write_json(
            target / "search.json",
            {"query": search.query, "results": [item.model_dump(mode="json") for item in search.results], "raw": search.raw},
        )
        record(
            "search",
            len(search.results) > 0,
            {
                "query": search.query,
                "n_results": len(search.results),
                "first_url": search_url,
                "titles": [item.title for item in search.results[:5]],
                "latency_ms": search.latency_ms,
            },
        )
    except DeepSeekError as error:
        record("search", False, {"error": str(error), "kind": error.kind, "status_code": error.status_code})

    # 5. Fetch a public source and read a slice through the evidence store.
    #    Try several public hosts; a publisher timeout is a source problem, not
    #    a reason to hammer the same URL or to fake success.
    preferred_hosts = (
        "ar5iv.labs.arxiv.org",
        "arxiv.org",
        "eegdash.org",
        "pmc.ncbi.nlm.nih.gov",
        "www.biorxiv.org",
        "elifesciences.org",
        "www.frontiersin.org",
        "www.nature.com",
    )

    def rank(url: str) -> int:
        for index, host in enumerate(preferred_hosts):
            if host in url:
                return index
        return len(preferred_hosts) + 1

    candidates: list[str] = []
    search_payload_path = target / "search.json"
    if search_payload_path.exists():
        try:
            saved = json.loads(search_payload_path.read_text(encoding="utf-8"))
            for item in saved.get("results", []):
                if isinstance(item, dict) and isinstance(item.get("url"), str):
                    candidates.append(item["url"].split("#", 1)[0])
        except (json.JSONDecodeError, OSError):
            pass
    candidates.extend(
        [
            "https://eegdash.org/concepts/leakage_and_evaluation.html",
            "https://ar5iv.labs.arxiv.org/html/2312.10987",
        ]
    )
    seen: set[str] = set()
    deduped: list[str] = []
    for candidate in candidates:
        cleaned = candidate.split("#", 1)[0]
        if cleaned.startswith(("http://", "https://")) and cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)
    ordered = sorted(deduped, key=rank)
    attempts: list[dict[str, object]] = []
    fetch_ok = False
    store = EvidenceStore(target / "evidence")
    for fetch_url in ordered[:6]:
        try:
            fetched = client.fetch(fetch_url)
            evidence = store.add_text(url=fetched.url, title=fetched.title, text=fetched.content, extractor="deepseek_fetch")
            sliced = store.read(evidence.evidence_id, start_char=0, max_chars=500, purpose="capability_check")
            attempts.append({"url": fetch_url, "ok": True, "chars": len(fetched.content), "evidence_id": evidence.evidence_id})
            atomic_write_json(
                target / "fetch.json",
                {
                    "url": fetched.url,
                    "title": fetched.title,
                    "chars": len(fetched.content),
                    "evidence_id": evidence.evidence_id,
                    "preview": fetched.content[:1000],
                    "attempts": attempts,
                },
            )
            record(
                "fetch_and_read",
                bool(fetched.content.strip()) and bool(sliced.text.strip()),
                {
                    "url": fetched.url,
                    "title": fetched.title,
                    "chars": len(fetched.content),
                    "evidence_id": evidence.evidence_id,
                    "slice_chars": len(sliced.text),
                    "page_start": sliced.page_start,
                    "attempts": attempts,
                },
            )
            fetch_ok = True
            break
        except DeepSeekError as error:
            attempts.append({"url": fetch_url, "ok": False, "error": str(error), "kind": error.kind, "status_code": error.status_code})
    if not fetch_ok:
        atomic_write_json(target / "fetch.json", {"attempts": attempts})
        record("fetch_and_read", False, {"attempts": attempts, "note": "all candidate public sources failed"})

    payload = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "model": "deepseek-flash",
        "provider": "deepseek_official",
        "checks": checks,
        "all_required_ok": all(item["ok"] for item in checks),
        "ledger": client.ledger.snapshot(),
        "note": "Engineering connectivity only; not a research result and not a model-capability benchmark.",
    }
    atomic_write_json(target / "capability.json", payload)
    atomic_write_text(target / "CAPABILITY_CHECK.md", _render_capability(payload))
    return payload


def _render_capability(payload: dict[str, object]) -> str:
    lines = [
        "# CAPABILITY CHECK",
        "",
        f"- started_at: {payload['started_at']}",
        f"- finished_at: {payload['finished_at']}",
        "- model: `deepseek-flash` via official Chat Completions",
        f"- all_required_ok: **{payload['all_required_ok']}**",
        "",
        "This is an engineering connectivity check, not a research result. A failure is reported, not mocked.",
        "",
        "| check | result | detail |",
        "|---|---|---|",
    ]
    for item in payload["checks"]:  # type: ignore[union-attr]
        detail = json.dumps(item["detail"], ensure_ascii=False, default=str)
        lines.append(f"| {item['name']} | {'PASS' if item['ok'] else 'FAIL'} | `{detail[:700]}` |")
    ledger = payload["ledger"]
    lines.extend(
        [
            "",
            "## Budget after capability check",
            "",
            "```json",
            json.dumps(ledger, indent=2, ensure_ascii=False),
            "```",
            "",
            "## Notes",
            "",
            "- The tool cycle verifies that assistant tool messages keep `reasoning_content` and tool messages keep `tool_call_id`.",
            "- Search and Fetch are real vendor requests; if Fetch fails on a URL, the failure is recorded above.",
            "- No Ollama or other provider was contacted.",
            "",
        ]
    )
    return "\n".join(lines)

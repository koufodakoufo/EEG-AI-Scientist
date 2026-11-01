"""Two-scope memory with a promotion filter.

tasks/<task>/memory/items/*.md   task memory: findings tied to one research question
memory/items/*.md                shared memory: facts that hold across EEG FM tasks

Each item is markdown with a YAML header (see templates/memory_item.md).
Rules enforced here (PROGRAM.md explains why):
  - every item cites evidence (attempt, document or URL);
  - no own test results while a run is in progress (test isolation);
  - items state facts / pitfalls / observations, not "what to try next"
    (prescriptive guidance narrows exploration; Dream-RSI 5.1);
  - promotion to shared memory requires a non-task scope (dataset, model,
    protocol, infra, domain) and either a fact or pitfall with a document/URL
    source, or confirmation from at least two tasks.
"""
import re
from pathlib import Path

import yaml

from eegfm.common import ROOT
from eegfm.common import now
from eegfm.common import read_json
from eegfm.common import task_dir

KINDS = {"fact", "pitfall", "observation"}
SCOPES = ("dataset:", "model:", "protocol:", "infra:", "domain:", "method:")
SHARED_SCOPES = ("dataset:", "model:", "protocol:", "infra:", "domain:")
PRESCRIPTIVE = re.compile(r"\b(should try|next we should|we should next|recommend(ed)? trying|must try)\b|下一步(应该|建议)|建议尝试", re.I)
OWN_TEST = re.compile(r"\btest\b[^\n]{0,40}?\d", re.I)


def folder(scope_task):
    return (task_dir(scope_task) / "memory" / "items") if scope_task else (ROOT / "memory" / "items")


def parse(path):
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{path}: missing YAML header")
    _, header, body = text.split("---", 2)
    return yaml.safe_load(header), body.strip()


def render(header, body):
    return "---\n" + yaml.safe_dump(header, sort_keys=False, allow_unicode=True) + "---\n\n" + body.strip() + "\n"


def validate(header, body, run=None):
    if header.get("kind") not in KINDS:
        raise SystemExit(f"kind must be one of {sorted(KINDS)}")
    applies = header.get("applies_to") or []
    if not applies or any(not str(a).startswith(SCOPES) for a in applies):
        raise SystemExit(f"applies_to entries must start with one of {SCOPES}")
    if not header.get("evidence"):
        raise SystemExit("evidence is required (run:<id>/attempt:<A#>, doc:<path> or url:<link>)")
    if PRESCRIPTIVE.search(body):
        raise SystemExit("Write the fact or pitfall, not a recommendation of what to try next")
    if run is not None and OWN_TEST.search(body):
        state = read_json(Path(run) / "STATE.json", {})
        if state.get("status") != "done":
            raise SystemExit("Own test results may enter memory only after the run is done")


def add(task_id, kind, claim, applies_to, evidence, confidence="medium", run=None, shared=False):
    header = {"id": None, "scope": "shared" if shared else f"task:{task_id}", "kind": kind,
              "applies_to": list(applies_to), "evidence": list(evidence), "confidence": confidence,
              "source_task": task_id, "confirmed_by_tasks": [task_id], "status": "active", "created": now()}
    validate(header, claim, run)
    if shared and not (kind in {"fact", "pitfall"} and any(str(e).startswith(("doc:", "url:")) for e in evidence)):
        raise SystemExit("Write directly to shared memory only for documented facts or pitfalls; otherwise add to the task and promote")
    target = folder(None if shared else task_id)
    target.mkdir(parents=True, exist_ok=True)
    stamp = now().replace(":", "").replace("-", "")[:15]
    count = len(list(target.glob("*.md"))) + 1
    header["id"] = f"{'S' if shared else 'T'}-{stamp}-{count:03d}"
    path = target / f"{header['id']}.md"
    path.write_text(render(header, claim), encoding="utf-8")
    index(task_id)
    return path


def promote(task_id, item_id, confirmed_by=()):
    source = folder(task_id) / f"{item_id}.md"
    if not source.exists():
        raise SystemExit(f"No task memory item {item_id}")
    header, body = parse(source)
    validate(header, body)
    header["confirmed_by_tasks"] = sorted(set(header.get("confirmed_by_tasks", [])) | set(confirmed_by))
    general = [a for a in header["applies_to"] if str(a).startswith(SHARED_SCOPES)]
    if not general:
        raise SystemExit("Only items about a dataset, model, protocol, infrastructure or the domain can be shared; "
                         "method-specific findings stay in task memory")
    documented = header["kind"] in {"fact", "pitfall"} and any(str(e).startswith(("doc:", "url:")) for e in header["evidence"])
    if not documented and len(header["confirmed_by_tasks"]) < 2:
        raise SystemExit("Promotion needs a documented fact or confirmation by at least two tasks")
    header.update(scope="shared", promoted_at=now(), promoted_from=f"task:{task_id}/{item_id}")
    target = folder(None)
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{item_id}.md").write_text(render(header, body), encoding="utf-8")
    source.unlink()
    index(task_id)
    return target / f"{item_id}.md"


def dispute(task_id, item_id, evidence, note):
    for path in [folder(task_id) / f"{item_id}.md", folder(None) / f"{item_id}.md"]:
        if path.exists():
            header, body = parse(path)
            header["status"] = "disputed"
            header.setdefault("disputes", []).append({"at": now(), "evidence": list(evidence), "note": note})
            path.write_text(render(header, body), encoding="utf-8")
            index(task_id)
            return path
    raise SystemExit(f"No memory item {item_id}")


def index(task_id=None):
    for scope_task in ([task_id] if task_id else []) + [None]:
        items = sorted(folder(scope_task).glob("*.md")) if folder(scope_task).exists() else []
        title = f"Task memory: {scope_task}" if scope_task else "Shared EEG FM memory"
        lines = [f"# {title}", "", "Generated by `eegfm memory index`. Facts and pitfalls with evidence; "
                 "not directions to pursue.", "", "| id | kind | applies to | status | confidence | claim |",
                 "|---|---|---|---|---|---|"]
        for path in items:
            header, body = parse(path)
            first = body.splitlines()[0][:140].replace("|", "/") if body else ""
            lines.append(f"| {header['id']} | {header['kind']} | {', '.join(header['applies_to'])} | "
                         f"{header.get('status')} | {header.get('confidence')} | {first} |")
        target = folder(scope_task).parent / "INDEX.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")

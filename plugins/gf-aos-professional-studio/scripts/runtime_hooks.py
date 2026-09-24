#!/usr/bin/env python3
"""Hook lifecycle GF-AOS senza accesso al transcript."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_INPUT_BYTES = 1024 * 1024
ALLOWED_EVENTS = {"PreCompact", "PostCompact", "SubagentStart", "Stop", "SessionEnd"}
MODULE_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,31}$")
ALLOWED_STATUSES = {
    "Da avviare", "In corso", "Completato", "Da validare",
    "In attesa documenti", "Bloccato", "Ignorato consapevolmente", "Approvato",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def alias_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def read_input() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError
    value = json.loads(raw.decode("utf-8")) if raw.strip() else {}
    if not isinstance(value, dict):
        raise ValueError
    return value


def workspace() -> Path | None:
    raw = os.environ.get("GF_AOS_WORKSPACE", "").strip()
    if not raw:
        return None
    lexical = Path(raw).expanduser()
    if lexical.is_symlink():
        raise ValueError
    root = lexical.resolve()
    if not root.is_dir():
        raise ValueError
    return root


def load_state(root: Path) -> dict[str, Any]:
    path = root / "CASE_STATE.json"
    if not path.is_file() or path.is_symlink():
        raise ValueError
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError
    if not isinstance(value.get("next_actions"), list) or len(value["next_actions"]) > 4:
        raise ValueError
    if not MODULE_RE.fullmatch(str(value.get("lead_module", ""))):
        raise ValueError
    if value.get("status") not in ALLOWED_STATUSES:
        raise ValueError
    return value


def memory_status(root: Path, state: dict[str, Any]) -> tuple[bool, str]:
    memory = root / "CASE_MEMORY.md"
    if not memory.is_file() or memory.is_symlink() or memory.stat().st_size > 512 * 1024:
        return False, "memoria canonica assente o non valida"
    checkpoint = state.get("current_checkpoint")
    if not isinstance(checkpoint, str) or not checkpoint.strip():
        return False, "checkpoint corrente assente"
    target = (root / checkpoint).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return False, "checkpoint fuori dal workspace"
    if not target.is_file() or target.is_symlink():
        return False, "checkpoint corrente assente"
    return True, "memoria canonica disponibile"


def append_event(root: Path, event: str, session_id: object) -> None:
    path = root / "EVENT_LOG.md"
    if not path.is_file() or path.is_symlink():
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"| {now_iso()} | {event} | session_ref={alias_hash(session_id)} |\n")


def output(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main() -> int:
    event = ""
    try:
        payload = read_input()
        event = str(payload.get("hook_event_name", ""))
        if event not in ALLOWED_EVENTS:
            return 0
        root = workspace()
        if root is None:
            return 0
        state = load_state(root)
        valid, message = memory_status(root, state)
        if event == "PreCompact":
            if not valid:
                output({"continue": False, "stopReason": "GF-AOS: aggiornare il checkpoint canonico prima della compattazione."})
                return 0
            output({"continue": True, "systemMessage": "GF-AOS: checkpoint canonico verificato; il transcript non viene acquisito."})
        elif event == "SubagentStart":
            context = (
                f"GF-AOS modulo {state.get('lead_module', 'NON_DEFINITO')}; stato {state.get('status', 'NON_DEFINITO')}. "
                "Usare solo il contesto minimo delegato; non dichiarare approvazioni o azioni esterne."
            )
            output({"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": context}})
        elif event == "Stop":
            output({"continue": True, "systemMessage": f"GF-AOS: {message}; nessun output è automaticamente approvato."})
        elif event == "PostCompact":
            append_event(root, "CONTEXT_COMPACTED", payload.get("session_id", ""))
        elif event == "SessionEnd":
            append_event(root, "SESSION_ENDED", payload.get("session_id", ""))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        if event == "PreCompact":
            output({"continue": False, "stopReason": "GF-AOS: controllo lifecycle non disponibile; aggiornare il checkpoint canonico."})
        else:
            output({"continue": True, "systemMessage": "GF-AOS: controllo lifecycle non disponibile; non assumere memoria o approvazioni."})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations
import json, hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Optional
from models import Outcome

GENESIS = "0" * 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(d: dict) -> str:
    # deterministic serialization — same content always hashes the same
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class LogEntry:
    seq: int
    timestamp: str
    action: dict
    decision: dict
    outcome: str
    result: Any
    error: Optional[str]
    prev_hash: str
    hash: str = ""

    def _content(self) -> dict:
        # everything the hash commits to: all fields except the hash itself
        d = asdict(self)
        d.pop("hash")
        return d

    def compute_hash(self) -> str:
        return hashlib.sha256(_canonical(self._content()).encode()).hexdigest()


class AuditLog:
    def __init__(self, path: str = "audit_log.jsonl"):
        self.path = path
        self.entries: list[LogEntry] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.entries.append(LogEntry(**json.loads(line)))
        except FileNotFoundError:
            pass

    @property
    def head_hash(self) -> str:
        return self.entries[-1].hash if self.entries else GENESIS

    def append(self, action, decision, outcome, result=None, error=None) -> LogEntry:
        entry = LogEntry(
            seq=len(self.entries),
            timestamp=_now(),
            action=action.to_dict() if hasattr(action, "to_dict") else dict(action),
            decision=decision.to_dict() if hasattr(decision, "to_dict") else dict(decision),
            outcome=outcome.value if isinstance(outcome, Outcome) else str(outcome),
            result=result,
            error=error,
            prev_hash=self.head_hash,          # links this entry to the one before
        )
        entry.hash = entry.compute_hash()
        with open(self.path, "a") as f:        # append-only: we never rewrite the file
            f.write(_canonical(asdict(entry)) + "\n")
        self.entries.append(entry)
        return entry

    def verify(self) -> tuple[bool, str]:
        prev = GENESIS
        for e in self.entries:
            if e.prev_hash != prev:
                return False, f"chain broken at seq {e.seq}: prev_hash mismatch"
            if e.compute_hash() != e.hash:
                return False, f"entry {e.seq} tampered: content no longer matches its hash"
            prev = e.hash
        return True, f"intact — {len(self.entries)} entries, head {prev[:12]}…"

    def query(self, actor=None, tool=None, effect=None,
              outcome=None, run_id=None) -> list[LogEntry]:
        def keep(e: LogEntry) -> bool:
            if actor   and e.action.get("actor")     != actor:   return False
            if tool    and e.action.get("tool")       != tool:    return False
            if effect  and e.decision.get("effect")   != effect:  return False
            if outcome and e.outcome                   != outcome: return False
            if run_id  and e.action.get("run_id")      != run_id:  return False
            return True
        return [e for e in self.entries if keep(e)]

    def replay(self, run_id: str) -> list[LogEntry]:
        # the full trail of one workflow, in the order it happened
        return sorted(self.query(run_id=run_id), key=lambda e: e.seq)


if __name__ == "__main__":
    import os
    from models import Action, Decision, Effect

    if os.path.exists("audit_log.jsonl"):
        os.remove("audit_log.jsonl")           # fresh run for a repeatable demo

    log = AuditLog()
    log.append(
        Action("libra-agent", "gdrive", "read", "Q3 deck", "user asked for a summary"),
        Decision(Effect.ALLOW, "allow by R1: reads are always safe", "R1"),
        Outcome.EXECUTED, result={"chars_read": 4120},
    )
    log.append(
        Action("libra-agent", "slack", "post_message", "#exec", "post the summary",
               params={"channel": "#exec"}),
        Decision(Effect.DENY, "deny by R4: sensitive channel is off-limits", "R4"),
        Outcome.BLOCKED,
    )
    log.append(
        Action("libra-agent", "gmail", "send", "client@acme.com", "send the recap"),
        Decision(Effect.REQUIRE_APPROVAL, "require_approval by R3: external recipient", "R3"),
        Outcome.PENDING,
    )

    ok, msg = log.verify()
    print("verify:", ok, "-", msg)

    print("\nevery denied action:")
    for e in log.query(effect="deny"):
        print(f"  seq {e.seq}: {e.action['tool']}.{e.action['action_type']} "
              f"-> {e.decision['reason']}")

    print("\n-- now someone edits seq 1 to hide the denial --")
    log.entries[1].decision["effect"] = "allow"
    log.entries[1].outcome = "executed"
    ok, msg = log.verify()
    print("verify:", ok, "-", msg)
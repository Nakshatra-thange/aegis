from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Effect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class Outcome(str, Enum):
    EXECUTED = "executed"
    BLOCKED = "blocked"
    PENDING = "pending"
    ERROR = "error"


@dataclass
class Action:
    actor: str                       # which agent proposed this
    tool: str                        # gmail, slack, gdrive...
    action_type: str                 # send, read, post_message...
    target: str                      # recipient, channel, doc name
    reason: str                      # the agent's own justification
    params: dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=_new_id)   # groups one workflow
    id: str = field(default_factory=_new_id)
    proposed_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decision:
    effect: Effect
    reason: str                      # always specific, never a bare bool
    matched_rule: str | None = None
    evaluated_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["effect"] = self.effect.value
        return d
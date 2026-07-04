from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from models import Action, Decision, Effect, Outcome


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PendingItem:
    action: Action
    decision: Decision
    log_seq: int                       # links back to the PENDING audit entry
    enqueued_at: str = field(default_factory=_now)


class ApprovalQueue:
    """Human-in-the-loop for actions the engine deferred. Every approve/reject
    is an audited event carrying the approver's identity and reason."""

    def __init__(self, gateway, log):
        self.gateway = gateway
        self.log = log
        self._pending: dict[str, PendingItem] = {}

    def enqueue(self, action: Action, decision: Decision, entry) -> None:
        self._pending[action.id] = PendingItem(action, decision, entry.seq)

    def list_pending(self) -> list[PendingItem]:
        return list(self._pending.values())

    def approve(self, action_id: str, approver: str, reason: str):
        item = self._require(action_id)
        del self._pending[action_id]
        # the human's ALLOW replaces the engine's REQUIRE_APPROVAL, then the
        # gateway executes and logs the outcome — one clean audited step.
        human = Decision(Effect.ALLOW,
                         f"approved by {approver}: {reason}",
                         matched_rule=f"human:{approver}")
        return self.gateway.execute_approved(item.action, human)

    def reject(self, action_id: str, approver: str, reason: str):
        item = self._require(action_id)
        del self._pending[action_id]
        human = Decision(Effect.DENY,
                         f"rejected by {approver}: {reason}",
                         matched_rule=f"human:{approver}")
        return self.log.append(item.action, human, Outcome.BLOCKED)

    def _require(self, action_id: str) -> PendingItem:
        item = self._pending.get(action_id)
        if item is None:
            raise KeyError(f"no pending action with id {action_id}")
        return item
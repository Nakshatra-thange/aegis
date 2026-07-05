from __future__ import annotations
from models import Action, Effect, Outcome
from policy import PolicyEngine
from audit import AuditLog
from executor import ToolRegistry, ToolError, registry as default_registry


class Gateway:
    def __init__(self, engine: PolicyEngine, log: AuditLog,
                 registry: ToolRegistry = default_registry, approvals=None):
        self.engine = engine
        self.log = log
        self.registry = registry
        self.approvals = approvals          # optional until approvals.py lands

    def submit(self, action: Action):
        """The single path every agent action takes. Nothing bypasses this."""
        decision = self.engine.evaluate(action)

        if decision.effect == Effect.DENY:
            return self.log.append(action, decision, Outcome.BLOCKED)

        if decision.effect == Effect.REQUIRE_APPROVAL:
            entry = self.log.append(action, decision, Outcome.PENDING)
            if self.approvals is not None:
                self.approvals.enqueue(action, decision, entry)
            return entry

        # ALLOW — and only here does a real tool call ever happen
        try:
            result = self.registry.run(action)
            return self.log.append(action, decision, Outcome.EXECUTED, result=result)
        except ToolError as e:
            return self.log.append(action, decision, Outcome.ERROR, error=str(e))
    def execute_approved(self, action: Action, human_decision):
        """Run an action a human explicitly approved. Reached only via the
        approval queue — the human's decision is what authorizes execution."""
        try:
            result = self.registry.run(action)
            return self.log.append(action, human_decision, Outcome.EXECUTED, result=result)
        except ToolError as e:
            return self.log.append(action, human_decision, Outcome.ERROR, error=str(e))


if __name__ == "__main__":
    import os
    from approvals import ApprovalQueue

    if os.path.exists("audit_log.jsonl"):
        os.remove("audit_log.jsonl")

    log = AuditLog()
    gw = Gateway(PolicyEngine.from_yaml("policies.yaml"), log)
    gw.approvals = ApprovalQueue(gw, log)      # attach after gateway exists

    # an external email gets deferred to a human
    email = Action("libra-agent", "gmail", "send", "client@acme.com",
                   "send the Q3 recap", params={"subject": "Q3 recap"})
    entry = gw.submit(email)
    print(f"submitted -> {entry.outcome}: {entry.decision['reason']}")

    pending = gw.approvals.list_pending()
    print(f"\npending queue has {len(pending)} item(s):")
    for p in pending:
        print(f"  {p.action.id}  {p.action.tool}.{p.action.action_type} -> {p.action.target}")

    # a human reviews and approves it
    print("\n-- Nakshatra reviews and approves --")
    result = gw.approvals.approve(email.id, approver="nakshatra",
                                  reason="client relationship is known, recap is accurate")
    print(f"after approval -> {result.outcome}: {result.decision['reason']}")

    print("\nfull trail for this workflow (run_id):")
    for e in log.replay(email.run_id):
        print(f"  seq {e.seq}: {e.decision['effect']:16} {e.outcome:9} {e.decision['reason']}")

    ok, msg = log.verify()
    print(f"\naudit chain: {'OK' if ok else 'TAMPERED'} - {msg}")
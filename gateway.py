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
    if os.path.exists("audit_log.jsonl"):
        os.remove("audit_log.jsonl")        # fresh run for a repeatable demo

    gw = Gateway(PolicyEngine.from_yaml("policies.yaml"), AuditLog())

    demo = [
        Action("libra-agent", "gdrive", "read", "Q3 board deck", "user asked for a summary"),
        Action("libra-agent", "slack", "post_message", "#exec", "post the summary",
               params={"channel": "#exec"}),
        Action("libra-agent", "gmail", "send", "client@acme.com", "send the recap",
               params={"subject": "Q3 recap"}),
        Action("libra-agent", "gmail", "send", "teammate@libra.ai", "internal fyi"),
        Action("libra-agent", "notion", "delete_page", "Roadmap", "cleanup"),
    ]

    print(f"{'action':28}{'target':20}{'outcome':10}reason")
    print("-" * 100)
    for a in demo:
        e = gw.submit(a)
        act = f"{a.tool}.{a.action_type}"
        print(f"{act:28}{a.target:20}{e.outcome:10}{e.decision['reason']}")

    ok, msg = gw.log.verify()
    print("-" * 100)
    print("audit chain:", "OK" if ok else "TAMPERED", "-", msg)
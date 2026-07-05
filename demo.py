from __future__ import annotations
import os, time
from models import Action
from policy import PolicyEngine
from audit import AuditLog
from gateway import Gateway
from approvals import ApprovalQueue

PAUSE = 1.2   # set to 0 for instant, raise for a slower on-camera pace


def hr(title: str = "") -> None:
    print("\n" + "=" * 78)
    if title:
        print(title)
        print("=" * 78)


def beat(msg: str) -> None:
    print(msg)
    time.sleep(PAUSE)


def show(entry, note: str) -> None:
    print(f"  → {entry.outcome.upper():9} | {note}")
    print(f"    reason: {entry.decision['reason']}")
    time.sleep(PAUSE)


def main() -> None:
    if os.path.exists("audit_log.jsonl"):
        os.remove("audit_log.jsonl")

    log = AuditLog()
    gw = Gateway(PolicyEngine.from_yaml("policies.yaml"), log)
    gw.approvals = ApprovalQueue(gw, log)

    hr("AEGIS — a governance layer for agent actions")
    beat("Every action an agent proposes passes through one gateway before it runs.\n"
         "The gateway checks policy, then logs the outcome — allowed or not.\n")

    hr("BEAT 1 — an allowed action executes")
    beat("The agent wants to read a Drive doc to summarize it.")
    show(gw.submit(Action("libra-agent", "gdrive", "read", "Q3 board deck",
                          "user asked for a summary")),
         "reads are safe, so it runs and is logged")

    hr("BEAT 2 — a forbidden action is blocked")
    beat("Now the agent tries to post that summary into #exec.")
    show(gw.submit(Action("libra-agent", "slack", "post_message", "#exec",
                          "post the summary", params={"channel": "#exec"})),
         "sensitive channel — blocked before anything is posted")

    hr("BEAT 3 — a gray-zone action waits for a human")
    beat("The agent wants to email an external client.")
    email = Action("libra-agent", "gmail", "send", "client@acme.com",
                   "send the Q3 recap", params={"subject": "Q3 recap"})
    show(gw.submit(email), "external recipient — held, not sent")

    beat("\nA human reviews the pending queue and signs off...")
    show(gw.approvals.approve(email.id, approver="nakshatra",
                              reason="known client, recap is accurate"),
         "human authorized it — now it sends, with their name on record")

    hr("BEAT 4 — an unknown action is denied by default")
    beat("The agent tries something no policy covers: deleting a Notion page.")
    show(gw.submit(Action("libra-agent", "notion", "delete_page", "Roadmap",
                          "cleanup")),
         "no rule permits it — deny by default")

    hr("THE TRAIL — replay the client-email workflow")
    for e in log.replay(email.run_id):
        print(f"  seq {e.seq}: {e.decision['effect']:16} {e.outcome:9} "
              f"{e.decision['reason']}")
    time.sleep(PAUSE)

    hr("TAMPER CHECK — the log can't be quietly rewritten")
    ok, msg = log.verify()
    print(f"  before: {'OK' if ok else 'TAMPERED'} — {msg}")
    log.entries[1].outcome = "executed"          # fake the blocked #exec post
    log.entries[1].decision["effect"] = "allow"
    ok, msg = log.verify()
    print(f"  after editing the blocked post to look allowed: "
          f"{'OK' if ok else 'TAMPERED'} — {msg}")
    beat("\nThe hash chain catches the edit. That's the whole point.")


if __name__ == "__main__":
    main()
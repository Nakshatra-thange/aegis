from __future__ import annotations
import argparse
from audit import AuditLog


def _short(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _row(e) -> str:
    act = f"{e.action['tool']}.{e.action['action_type']}"
    return (f"{e.seq:>3}  {_short(e.action['actor'],12):12}  "
            f"{_short(act,22):22}  {_short(e.action['target'],18):18}  "
            f"{e.decision['effect']:16}  {e.outcome:9}  "
            f"{_short(e.decision['reason'],44)}")


_HEADER = (f"{'seq':>3}  {'actor':12}  {'action':22}  {'target':18}  "
           f"{'effect':16}  {'outcome':9}  reason")


def _print_table(entries) -> None:
    if not entries:
        print("(no matching entries)")
        return
    print(_HEADER)
    print("-" * 120)
    for e in entries:
        print(_row(e))


def _latest_outcome_by_action(log: AuditLog) -> dict[str, str]:
    latest: dict[str, str] = {}
    for e in log.entries:           # entries are in append order
        latest[e.action["id"]] = e.outcome
    return latest


def cmd_log(log: AuditLog, args) -> None:
    entries = log.query(actor=args.actor, tool=args.tool,
                        effect=args.effect, run_id=args.run)
    _print_table(entries)


def cmd_pending(log: AuditLog, args) -> None:
    latest = _latest_outcome_by_action(log)
    still_pending = [e for e in log.entries
                     if e.outcome == "pending" and latest[e.action["id"]] == "pending"]
    print(f"{len(still_pending)} action(s) awaiting human approval:\n")
    _print_table(still_pending)


def cmd_replay(log: AuditLog, args) -> None:
    entries = log.replay(args.run_id)
    print(f"full trail for run {args.run_id}:\n")
    _print_table(entries)


def cmd_verify(log: AuditLog, args) -> None:
    ok, msg = log.verify()
    print(f"audit chain: {'OK' if ok else 'TAMPERED'} — {msg}")


def main() -> None:
    p = argparse.ArgumentParser(prog="aegis", description="view the agent audit log")
    p.add_argument("--file", default="audit_log.jsonl", help="log file to read")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("log", help="show the full audit table")
    lg.add_argument("--actor")
    lg.add_argument("--tool")
    lg.add_argument("--effect", choices=["allow", "deny", "require_approval"])
    lg.add_argument("--run")
    lg.set_defaults(func=cmd_log)

    pn = sub.add_parser("pending", help="actions awaiting approval")
    pn.set_defaults(func=cmd_pending)

    rp = sub.add_parser("replay", help="full trail of one workflow")
    rp.add_argument("run_id")
    rp.set_defaults(func=cmd_replay)

    vf = sub.add_parser("verify", help="check the hash chain")
    vf.set_defaults(func=cmd_verify)

    args = p.parse_args()
    log = AuditLog(args.file)
    args.func(log, args)


if __name__ == "__main__":
    main()
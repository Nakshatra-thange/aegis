import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Action, Decision, Effect, Outcome
from audit import AuditLog


def fresh_log():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)                 # AuditLog creates it on first append
    return AuditLog(path), path


def _add(log, effect=Effect.ALLOW, outcome=Outcome.EXECUTED):
    log.append(
        Action("libra-agent", "gdrive", "read", "doc", "reason"),
        Decision(effect, "test reason"),
        outcome,
    )


def test_chain_verifies_when_untouched():
    log, path = fresh_log()
    for _ in range(3):
        _add(log)
    ok, _ = log.verify()
    assert ok
    os.remove(path)


def test_tampering_with_content_is_detected():
    log, path = fresh_log()
    _add(log, Effect.DENY, Outcome.BLOCKED)
    _add(log)
    log.entries[0].decision["effect"] = "allow"   # rewrite history
    ok, msg = log.verify()
    assert not ok and "tampered" in msg
    os.remove(path)


def test_reload_from_disk_preserves_chain():
    log, path = fresh_log()
    for _ in range(3):
        _add(log)
    reloaded = AuditLog(path)                      # read back from file
    ok, _ = reloaded.verify()
    assert ok and len(reloaded.entries) == 3
    os.remove(path)
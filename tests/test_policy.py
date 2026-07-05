import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Action, Effect
from policy import PolicyEngine


def engine():
    path = os.path.join(os.path.dirname(__file__), "..", "policies.yaml")
    return PolicyEngine.from_yaml(path)


def test_unlisted_action_is_denied_by_default():
    d = engine().evaluate(
        Action("libra-agent", "notion", "delete_page", "Roadmap", "cleanup"))
    assert d.effect == Effect.DENY
    assert "default" in d.reason


def test_external_email_requires_approval():
    d = engine().evaluate(
        Action("libra-agent", "gmail", "send", "client@acme.com", "recap"))
    assert d.effect == Effect.REQUIRE_APPROVAL


def test_internal_email_is_allowed():
    d = engine().evaluate(
        Action("libra-agent", "gmail", "send", "teammate@libra.ai", "fyi"))
    assert d.effect == Effect.ALLOW


def test_sensitive_channel_is_denied():
    d = engine().evaluate(
        Action("libra-agent", "slack", "post_message", "#exec", "post",
               params={"channel": "#exec"}))
    assert d.effect == Effect.DENY


def test_general_channel_is_allowed():
    d = engine().evaluate(
        Action("libra-agent", "slack", "post_message", "#general", "post",
               params={"channel": "#general"}))
    assert d.effect == Effect.ALLOW


def test_deny_wins_precedence():
    # if both an allow and a deny rule matched, deny must win
    from policy import Rule, PolicyEngine as PE
    eng = PE([
        Rule("A", "x", "y", Effect.ALLOW),
        Rule("D", "x", "y", Effect.DENY),
    ])
    assert eng.evaluate(Action("a", "x", "y", "t", "r")).effect == Effect.DENY
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
from models import Action, Decision, Effect
import yaml
_MISSING = object()


def _resolve(data: dict, path: str):
    """Read a dotted path out of the action dict, e.g. 'params.channel'."""
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _domain(addr: str) -> str:
    return addr.split("@")[-1].lower() if addr else ""


# operator registry — add a new comparison here, not in the engine logic
_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "equals":         lambda a, e: a == e,
    "not_equals":     lambda a, e: a != e,
    "in":             lambda a, e: a in e,
    "not_in":         lambda a, e: a not in e,
    "domain_in":      lambda a, e: _domain(a) in [x.lower() for x in e],
    "domain_not_in":  lambda a, e: _domain(a) not in [x.lower() for x in e],
}


@dataclass
class Condition:
    field: str
    op: str
    value: Any

    def holds(self, action_dict: dict) -> bool:
        actual = _resolve(action_dict, self.field)
        if actual is _MISSING:      # missing field never satisfies a condition
            return False
        return _OPS[self.op](actual, self.value)


@dataclass
class Rule:
    id: str
    tool: str
    action_type: str
    effect: Effect
    actor: str | None = None        # None = applies to every agent
    when: list[Condition] = field(default_factory=list)
    description: str = ""

    def matches(self, action: Action) -> bool:
        if self.tool != action.tool or self.action_type != action.action_type:
            return False
        if self.actor is not None and self.actor != action.actor:
            return False
        d = action.to_dict()
        return all(c.holds(d) for c in self.when)   # all conditions must hold


class PolicyEngine:
    # most restrictive effect wins among matching rules
    _PRECEDENCE = {Effect.DENY: 0, Effect.REQUIRE_APPROVAL: 1, Effect.ALLOW: 2}

    def __init__(self, rules: list[Rule]):
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: str) -> "PolicyEngine":

        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        rules = []
        for i, r in enumerate(raw.get("rules", [])):
            conds = []
            for c in r.get("when", []):
                if c["op"] not in _OPS:                     # fail fast on bad config
                    raise ValueError(f"unknown operator: {c['op']}")
                conds.append(Condition(c["field"], c["op"], c["value"]))
            rules.append(Rule(
                id=r.get("id", f"R{i+1}"),
                tool=r["tool"],
                action_type=r["action_type"],
                effect=Effect(r["effect"]),
                actor=r.get("actor"),
                when=conds,
                description=r.get("description", ""),
            ))
        return cls(rules)

    def evaluate(self, action: Action) -> Decision:
        matched = [r for r in self.rules if r.matches(action)]
        if not matched:                                     # deny by default
            return Decision(
                effect=Effect.DENY,
                reason=(f"no rule permits {action.tool}.{action.action_type} "
                        f"for '{action.actor}' — deny by default"),
            )
        winner = min(matched, key=lambda r: self._PRECEDENCE[r.effect])
        reason = f"{winner.effect.value} by {winner.id}"
        if winner.description:
            reason += f": {winner.description}"
        return Decision(effect=winner.effect, reason=reason, matched_rule=winner.id)


if __name__ == "__main__":
    engine = PolicyEngine.from_yaml("policies.yaml")
    samples = [
        Action("libra-agent", "gdrive", "read", "Q3 board deck", "user asked for a summary"),
        Action("libra-agent", "slack", "post_message", "#exec", "posting the summary",
               params={"channel": "#exec"}),
        Action("libra-agent", "gmail", "send", "client@acme.com", "sending the recap"),
        Action("libra-agent", "gmail", "send", "teammate@libra.ai", "internal fyi"),
        Action("libra-agent", "notion", "delete_page", "Roadmap", "cleanup"),
    ]
    for a in samples:
        d = engine.evaluate(a)
        print(f"{a.tool + '.' + a.action_type:22} {a.target:20} "
              f"{d.effect.value.upper():16} {d.reason}")
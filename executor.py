from __future__ import annotations
from typing import Callable
from models import Action

ToolFn = Callable[[Action], dict]


class ToolError(Exception):
    """Raised when an allowed action has no adapter, or an adapter fails."""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[tuple[str, str], ToolFn] = {}

    def register(self, tool: str, action_type: str):
        def deco(fn: ToolFn) -> ToolFn:
            self._tools[(tool, action_type)] = fn
            return fn
        return deco

    def run(self, action: Action) -> dict:
        fn = self._tools.get((action.tool, action.action_type))
        if fn is None:
            # a rule allowed something we have no adapter for — surfaces as ERROR,
            # never a silent no-op. The gateway catches this and logs it.
            raise ToolError(f"no adapter for {action.tool}.{action.action_type}")
        return fn(action)


registry = ToolRegistry()


@registry.register("gdrive", "read")
def gdrive_read(a: Action) -> dict:
    return {"status": "ok", "doc": a.target, "chars_read": 4120}


@registry.register("gmail", "read")
def gmail_read(a: Action) -> dict:
    return {"status": "ok", "mailbox": a.target, "messages": 12}


@registry.register("gmail", "send")
def gmail_send(a: Action) -> dict:
    return {"status": "sent", "to": a.target,
            "subject": a.params.get("subject", "(no subject)")}


@registry.register("slack", "post_message")
def slack_post(a: Action) -> dict:
    return {"status": "posted", "channel": a.params.get("channel", a.target)}


@registry.register("linear", "create_issue")
def linear_create_issue(a: Action) -> dict:
    return {"status": "created", "issue": "LIB-241", "title": a.target}


if __name__ == "__main__":
    a = Action("libra-agent", "gmail", "send", "client@acme.com",
               "send the recap", params={"subject": "Q3 recap"})
    print(registry.run(a))
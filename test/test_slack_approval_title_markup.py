"""A tool approval card on Slack cannot be made to mention anyone by its tool title.

The title and purpose of a permission request carry model-chosen text: an
execute call's title is its command line, and the purpose is the model's own
description of it. Slack parses entity markup (``<!channel>``, ``<!here>``,
``<@U…>``) in a ``mrkdwn`` block field AND in a message's top-level text, which
is what notifications show. So a command such as ``echo "<!channel>"`` -- one a
prompt-injected page can talk the model into proposing -- would notify a whole
channel the moment its approval card is posted, or rewritten once answered.
Every sink escapes it with ``escape_mrkdwn`` after redaction.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kiro_crew.llm_helpers import LLMEvent
from kiro_crew.slack import handler
from kiro_crew.slack.handler import _build_approval_blocks, _PendingApproval

TITLE = 'Running: echo "<!channel> <@U0123ABCD> deploy"'
PURPOSE = "Tell <!here> the deploy is done"
MENTIONS = ("<!channel>", "<!here>", "<@U0123ABCD>")


def _event(**overrides) -> LLMEvent:
    fields = {"kind": "permission_request", "request_id": "req1", "title": TITLE}
    fields.update(overrides)
    return LLMEvent(**fields)


def _block_texts(blocks: list[dict]) -> list[str]:
    texts: list[str] = []
    for block in blocks:
        if isinstance(block.get("text"), dict):
            texts.append(block["text"]["text"])
        for element in block.get("elements", ()):
            if isinstance(element.get("text"), str):
                texts.append(element["text"])
    return texts


def _assert_inert(text: str) -> None:
    for mention in MENTIONS:
        assert mention not in text, text


class TestCardBlocks:
    def test_the_footer_escapes_the_title_and_the_purpose(self) -> None:
        blocks = _build_approval_blocks(_event(tool_purpose=PURPOSE))
        [footer] = [b for b in blocks if b["type"] == "context"]
        text = footer["elements"][0]["text"]
        _assert_inert(text)
        assert "&lt;!channel&gt;" in text and "&lt;!here&gt;" in text

    def test_redaction_still_runs_before_the_escape(self) -> None:
        token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
        blocks = _build_approval_blocks(_event(title=f"Running: echo {token} <!channel>"))
        for text in _block_texts(blocks):
            assert token not in text
            _assert_inert(text)


def _gateway():
    from kiro_crew.slack.gateway import GatewayOrchestrator

    gw = GatewayOrchestrator.__new__(GatewayOrchestrator)
    gw.sessions = MagicMock()
    gw.sessions.get_pid = MagicMock(return_value=None)
    gw.sessions.get_channel = MagicMock(return_value=None)
    gw.sessions.get_thread = MagicMock(return_value=None)
    gw.slack = MagicMock()
    gw.slack.post_blocks = AsyncMock(return_value="approval_ts")
    gw.slack.update_message = AsyncMock()
    gw.dashboard_state = MagicMock()
    gw.dashboard_state._yolo = False
    gw.dashboard_state._slots = {}
    gw.dashboard_state.request_approval = AsyncMock(return_value=True)
    gw.dashboard_state.resolve_approval = MagicMock()
    gw._owner_id = "U000"
    gw._cfg = MagicMock()
    gw._cfg.hooks.get = MagicMock(return_value=[])
    gw._cfg.agent.max_subagents = 4
    gw._approval_mode = None
    return gw


class TestGatewayCard:
    @pytest.mark.asyncio
    async def test_the_fallback_and_the_answered_card_are_inert(self) -> None:
        gw = _gateway()
        # Routed to the parent conversation's thread, so the card posts there.
        gw.sessions.get_channel = MagicMock(return_value="C_PARENT")
        gw.sessions.get_thread = MagicMock(return_value="1775113012.860459")
        pending = _PendingApproval(provider=None, request_id="req1")  # type: ignore[arg-type]
        pending.future.set_result("approved")
        with (
            patch("kiro_crew.slack.handler.is_yolo_mode", return_value=False),
            patch("kiro_crew.slack.handler._PendingApproval", return_value=pending),
        ):
            approve = gw._interactive_approval("subagent")
            assert await approve(_event(), "1775113012.860459") is True

        _channel, _blocks, fallback, _thread = gw.slack.post_blocks.await_args.args
        _assert_inert(fallback)
        assert "&lt;!channel&gt;" in fallback
        answered = gw.slack.update_message.await_args.kwargs["text"]
        _assert_inert(answered)
        assert "&lt;!channel&gt;" in answered


class TestNativeCard:
    @pytest.mark.asyncio
    async def test_the_answered_card_is_inert_when_the_prompt_cannot_be_deleted(
        self, monkeypatch
    ) -> None:
        async def _expire(awaitable, timeout):
            # The prompt goes unanswered: the window runs out at once.
            raise TimeoutError

        async def _delete(*_args, **_kwargs):
            raise RuntimeError("message_not_found")

        updates: list[str] = []

        async def _update(_slack, _channel, _ts, text):
            updates.append(text)

        monkeypatch.setattr(handler, "_APPROVAL_TIMEOUT", 600.0)
        monkeypatch.setattr(handler.asyncio, "wait_for", _expire)
        monkeypatch.setattr(handler, "_steer_host_deny", AsyncMock())
        monkeypatch.setattr(handler, "_safe_update", _update)
        monkeypatch.setattr(handler, "Stats", lambda: SimpleNamespace(inc_tool_denial=lambda: None))
        slack = SimpleNamespace(
            post_blocks=AsyncMock(return_value="1.0001"), delete_message=_delete
        )
        provider = SimpleNamespace(reject_tool=AsyncMock())

        await handler._request_approval(slack, provider, "D1", "1.0", _event(), "s")

        [answered] = updates
        _assert_inert(answered)
        assert "&lt;!channel&gt;" in answered

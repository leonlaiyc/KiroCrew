"""How an ``AcpSessionProvider`` tears its session down, per runtime owner.

:func:`shutdown_session` is the body of ``AcpSessionProvider.shutdown`` once the
local MCP launch snapshots are accounted for. It has three arms: a chat on a
SHARED runtime leaves the process (``acp.session_provider_shared``); a provider
that owns its runtime releases its lease and kills it; a session-sharing
subagent cancels its turn and destroys only its own handle, because co-tenant
sessions still run on that process.

Each function here whose first parameter is ``self`` is an ``AcpSessionProvider``
method: the class binds it by name, so it reads and writes the provider's own
state on the instance, and a patch of the method on the class or on an instance
reaches every caller.

Instance fields written: ``_session_claim``, and ``subagent_departed`` on the
runtime.

Instance fields read: ``_handle``, ``_owns_runtime``, ``_runtime``,
``_session_claim``, ``_shared_runtime``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from kiro_crew.acp import session_provider_shared as _sp_shared

if TYPE_CHECKING:
    from kiro_crew.acp.session_provider import AcpSessionProvider

#: The provider's logger: this code logged under that name before the split.
logger = logging.getLogger("kiro_crew.acp.session_provider")


async def shutdown_session(self: AcpSessionProvider) -> None:
    """End this provider's session: leave, kill or detach, by runtime owner."""
    if getattr(self, "_shared_runtime", False):
        await self._shutdown_shared()
        return
    if self._owns_runtime:
        # A runtime kill cancels only its reader tasks, so the handle's own
        # in-flight hook executions are stopped here first.
        cancel_hooks = getattr(self._handle, "_cancel_hook_tasks", None)
        if callable(cancel_hooks):
            cancel_hooks()
        # Release BEFORE the kill, and before the destroy that precedes it.
        # From this line on this provider is committed to ending the runtime,
        # so holding the lease any longer would only make the gate refuse
        # this teardown -- the process's owner refusing its own kill.
        #
        # Releasing first also covers the paths that never reach the kill
        # below. A cancellation delivered into this coroutine leaves the
        # process alive exactly as it does today, and the hard-kill fallback
        # that cleans up after it then finds no lease and is authorized. Were
        # the release after the kill, that fallback would be refused and the
        # leak it exists to prevent would become permanent.
        await self.release_runtime_lease()
        killed = False
        try:
            if self.memory_mode != "persistent":
                try:
                    await self._handle.destroy()
                finally:
                    await self._runtime.kill(
                        expected=True, reason="provider shutdown (non-persistent)"
                    )
            else:
                await self._runtime.kill(expected=True, reason="provider shutdown")
            killed = True
        except Exception:
            logger.debug("AcpSessionProvider.shutdown: runtime kill failed", exc_info=True)
        closed = False
        try:
            closed = await self._close_own_session_left_on_process()
        finally:
            # The kill returning is not evidence the app servers under it are
            # gone: a descendant that left the process group survives it. Only a
            # whole tree confirmed dead settles the close
            # (``_sp_shared.teardown_confirmed``), or, on a process a refused kill
            # left alive, the host's answer to the close sent above.
            sid = getattr(self._handle, "session_id", None)
            if not closed and not (
                killed and _sp_shared.teardown_confirmed(self._runtime, sid, killed=True)
            ):
                _sp_shared.note_unconfirmed_teardown(self, self._runtime, sid)
    else:
        # Session-sharing subagent: the runtime is SHARED with co-tenant
        # sessions (parent + sibling subagents), so we must NOT kill it.
        # But destroy() only unregisters this session's queue — it does not
        # tell kiro-cli to stop an in-flight prompt. Reaping a subagent
        # mid-turn (timeout / user cancel) would otherwise leave the abandoned
        # prompt running on the shared process: it keeps burning credits, its
        # frames get dropped (unknown-session), and it can wedge the next
        # prompt on that sessionId with "already in progress". So cancel the
        # session's turn first (best-effort, bounded so an unresponsive
        # runtime can't turn shutdown into a hang), then destroy the handle.
        # The destroy is in a `finally` because the cancel above can be
        # left through a door `except Exception` does not cover:
        # `asyncio.CancelledError` is a `BaseException`. That is not a
        # theoretical exit — the session-restart path runs
        # `asyncio.wait_for(p.shutdown(), timeout=_SHUTDOWN_TIMEOUT_SECS)`
        # inside an `asyncio.gather`, so both a shutdown that outruns the
        # budget and a cancelled restart task deliver a cancellation into
        # this coroutine, at whatever await it is sitting on.
        #
        # Sequentially, that skipped the destroy entirely — and the destroy
        # is where this arm's two invariants live: `terminate_session`
        # evicts the session from the SHARED kiro-cli process (it is the
        # only RSS reclaim on a runtime nothing here is allowed to kill),
        # and the transcript unlink is the only thing that removes
        # `~/.kiro/sessions/cli/{sid}.json(+.jsonl)`, as the comment below
        # says. Nothing retries: every caller drops the provider afterwards.
        # Before the first await, so a sharing decision made meanwhile sees it.
        self._runtime.subagent_departed = True
        try:
            try:
                if self._handle.is_turn_active and not self.turn_survives_disconnect:
                    try:
                        await asyncio.wait_for(self._handle.cancel(), timeout=5.0)
                    except Exception:
                        logger.debug(
                            "AcpSessionProvider.shutdown: session cancel failed", exc_info=True
                        )
            finally:
                destroyed = False
                try:
                    if (
                        getattr(self._handle, "keep_transcript", False) is True
                        and self._runtime.can_release() is True
                    ):
                        # A host whose teardown verb deletes the record (KAS) but
                        # that can free a session and keep it: the record is
                        # ``spawn_continue``'s resume material, so the session is
                        # closed instead, and the tombstone pruner deletes the
                        # record with the run folder.
                        with self._runtime.keep_record_on_teardown(self._handle.session_id):
                            await self._handle.destroy()
                    else:
                        await self._handle.destroy()
                    destroyed = True
                except Exception:
                    logger.debug("AcpSessionProvider.shutdown: destroy failed", exc_info=True)
                # Same judge as every other teardown branch (``teardown_confirmed``).
                sub_sid = getattr(self._handle, "session_id", None)
                if not (
                    destroyed
                    and _sp_shared.teardown_confirmed(self._runtime, sub_sid, killed=False)
                ):
                    _sp_shared.note_unconfirmed_teardown(self, self._runtime, sub_sid)
        finally:
            # After the close, so the last party off an orphaned process ends it
            # only once this session has left it (``hold_shared_session``).
            claim, self._session_claim = getattr(self, "_session_claim", None), None
            await self._end_shared_turn(claim)
        # destroy() deletes the shared-subagent session transcript
        # (~/.kiro/sessions/cli/{sid}.json+.jsonl); no separate cleanup call
        # needed. ``AcpSessionProvider.cleanup_session`` remains for the LLMProvider API.

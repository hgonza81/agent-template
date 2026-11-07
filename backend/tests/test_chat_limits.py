import asyncio

import pytest

from agent_template_api.chat_limits import (
    ClientDisconnectedError,
    ConcurrencyLimiter,
    RateLimiter,
    run_until_disconnect,
)


def test_concurrency_limiter_rejects_over_the_limit_and_recovers() -> None:
    limiter = ConcurrencyLimiter(2)

    assert limiter.try_acquire()
    assert limiter.try_acquire()
    assert not limiter.try_acquire()
    limiter.release()
    assert limiter.try_acquire()
    limiter.release()
    limiter.release()
    limiter.release()  # extra releases never go negative
    assert limiter.active == 0


def test_rate_limiter_uses_a_sliding_window_per_key() -> None:
    now = [0.0]
    limiter = RateLimiter(2, window_seconds=60, clock=lambda: now[0])

    assert limiter.check("a") is None
    now[0] = 10
    assert limiter.check("a") is None
    assert limiter.check("b") is None  # other keys are independent
    assert limiter.check("a") == 50  # oldest hit expires at t=60
    now[0] = 60.5
    assert limiter.check("a") is None


def test_rate_limiter_forgets_idle_keys() -> None:
    now = [0.0]
    limiter = RateLimiter(1, window_seconds=60, clock=lambda: now[0])
    limiter.check("a")
    now[0] = 120
    limiter.check("b")

    assert "a" not in limiter._hits


class FakeRequest:
    def __init__(self, disconnect_after_polls: int | None = None) -> None:
        self.polls = 0
        self._after = disconnect_after_polls

    async def is_disconnected(self) -> bool:
        self.polls += 1
        return self._after is not None and self.polls >= self._after


def test_run_until_disconnect_returns_the_result() -> None:
    async def work() -> str:
        return "done"

    assert asyncio.run(run_until_disconnect(FakeRequest(), work())) == "done"


def test_run_until_disconnect_cancels_work_when_the_client_leaves() -> None:
    state = {"cancelled": False}

    async def work() -> str:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        return "never"

    async def scenario() -> None:
        await run_until_disconnect(FakeRequest(1), work(), poll_seconds=0.01)

    with pytest.raises(ClientDisconnectedError):
        asyncio.run(scenario())
    assert state["cancelled"]


def test_run_until_disconnect_cancels_work_when_the_caller_is_cancelled() -> None:
    state = {"cancelled": False}

    async def work() -> str:
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        return "never"

    async def scenario() -> None:
        task = asyncio.ensure_future(
            run_until_disconnect(FakeRequest(), work(), poll_seconds=0.01)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert state["cancelled"]

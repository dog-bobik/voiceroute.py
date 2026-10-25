from voiceroute import RateLimiter


async def test_rate_limiter_waits_for_sliding_window() -> None:
    now = 0.0
    delays: list[float] = []

    def clock() -> float:
        return now

    async def sleep(delay: float) -> None:
        nonlocal now
        delays.append(delay)
        now += delay

    limiter = RateLimiter(limit=2, period=1.0, clock=clock, sleep=sleep)

    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()

    assert delays == [1.0]


def test_rate_limiter_validates_configuration() -> None:
    for kwargs in ({"limit": 0}, {"period": 0}):
        try:
            RateLimiter(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid rate limiter configuration was accepted")

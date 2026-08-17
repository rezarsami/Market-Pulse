from app.guardrails.rate_limiter import RateLimiter


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = RateLimiter(per_minute=5, per_day=100)
        for _ in range(5):
            decision = rl.check_and_record("client-a")
            assert decision.allowed

    def test_blocks_over_minute_limit(self):
        rl = RateLimiter(per_minute=3, per_day=100)
        for _ in range(3):
            assert rl.check_and_record("client-b").allowed
        decision = rl.check_and_record("client-b")
        assert not decision.allowed
        assert "minute" in decision.reason

    def test_blocks_over_day_limit(self):
        rl = RateLimiter(per_minute=1000, per_day=2)
        assert rl.check_and_record("client-c").allowed
        assert rl.check_and_record("client-c").allowed
        decision = rl.check_and_record("client-c")
        assert not decision.allowed
        assert "daily" in decision.reason

    def test_different_clients_independent(self):
        rl = RateLimiter(per_minute=1, per_day=100)
        assert rl.check_and_record("client-x").allowed
        # client-y should not be affected by client-x's usage
        assert rl.check_and_record("client-y").allowed
        # client-x is now over its limit
        assert not rl.check_and_record("client-x").allowed

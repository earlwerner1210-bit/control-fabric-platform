from __future__ import annotations


class TestInputSanitiser:
    def test_strips_html_tags(self) -> None:
        from app.core.security_hardening.input_sanitiser import sanitise_string

        result = sanitise_string("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result

    def test_truncates_to_max_length(self) -> None:
        from app.core.security_hardening.input_sanitiser import sanitise_string

        long_str = "a" * 5000
        result = sanitise_string(long_str, field_type="default")
        assert len(result) <= 2048

    def test_sanitise_identifier_strips_dangerous_chars(self) -> None:
        from app.core.security_hardening.input_sanitiser import sanitise_identifier

        result = sanitise_identifier("tenant-001; DROP TABLE users--")
        assert ";" not in result
        assert " " not in result
        assert "tenant-001" in result

    def test_sanitise_dict_recursive(self) -> None:
        from app.core.security_hardening.input_sanitiser import sanitise_dict

        data = {
            "name": "<b>Test</b>",
            "nested": {"email": "<script>xss</script>admin@test.com"},
        }
        result = sanitise_dict(data)
        assert "<b>" not in result.get("name", "")
        assert "<script>" not in str(result)

    def test_url_validation_blocks_javascript(self) -> None:
        from app.core.security_hardening.input_sanitiser import validate_url

        valid, reason = validate_url("javascript:alert(1)")
        assert valid is False
        assert "javascript" in reason.lower()

    def test_url_validation_allows_https(self) -> None:
        from app.core.security_hardening.input_sanitiser import validate_url

        valid, reason = validate_url("https://api.example.com/webhook")
        assert valid is True


class TestTenantRateLimiter:
    def test_within_limit_allowed(self) -> None:
        from app.core.security_hardening.tenant_rate_limiter import TenantRateLimiter

        limiter = TenantRateLimiter()
        allowed, detail = limiter.check("tenant-test-rl", "requests_per_minute")
        assert allowed is True

    def test_enterprise_unlimited_for_reconciliation(self) -> None:
        from app.core.security_hardening.tenant_rate_limiter import (
            TIER_LIMITS,
            TenantRateLimiter,
        )

        limiter = TenantRateLimiter()
        limiter.set_tier("enterprise-test", "enterprise")
        assert TIER_LIMITS["enterprise"]["reconciliation_per_hour"] == -1
        allowed, detail = limiter.check("enterprise-test", "reconciliation_per_hour")
        assert allowed is True
        assert detail == "unlimited"

    def test_tier_limits_correct(self) -> None:
        from app.core.security_hardening.tenant_rate_limiter import TIER_LIMITS

        assert (
            TIER_LIMITS["starter"]["requests_per_minute"]
            < TIER_LIMITS["enterprise"]["requests_per_minute"]
        )
        assert (
            TIER_LIMITS["growth"]["requests_per_minute"]
            < TIER_LIMITS["enterprise"]["requests_per_minute"]
        )


class TestNotificationManager:
    def test_set_and_get_preference(self) -> None:
        from app.core.notifications.manager import NotificationManager
        from app.core.notifications.preferences import NotificationChannel, NotificationEvent

        mgr = NotificationManager()
        pref = mgr.set_preference(
            user_id="user-001",
            tenant_id="test",
            event=NotificationEvent.CRITICAL_CASE_DETECTED,
            channel=NotificationChannel.EMAIL,
            destination="ops@company.com",
        )
        assert pref.event == NotificationEvent.CRITICAL_CASE_DETECTED
        prefs = mgr.get_preferences("user-001", "test")
        assert len(prefs) == 1

    def test_overwrite_existing_preference(self) -> None:
        from app.core.notifications.manager import NotificationManager
        from app.core.notifications.preferences import NotificationChannel, NotificationEvent

        mgr = NotificationManager()
        mgr.set_preference(
            "u1", "t1", NotificationEvent.SLA_BREACH, NotificationChannel.EMAIL, "a@b.com"
        )
        mgr.set_preference(
            "u1", "t1", NotificationEvent.SLA_BREACH, NotificationChannel.EMAIL, "c@d.com"
        )
        prefs = mgr.get_preferences("u1")
        assert len(prefs) == 1
        assert prefs[0].destination == "c@d.com"

    def test_get_subscribers_for_event(self) -> None:
        from app.core.notifications.manager import NotificationManager
        from app.core.notifications.preferences import NotificationChannel, NotificationEvent

        mgr = NotificationManager()
        mgr.set_preference(
            "u1",
            "tenant-a",
            NotificationEvent.RELEASE_BLOCKED,
            NotificationChannel.SLACK,
            "https://hooks.slack.com/test",
        )
        mgr.set_preference(
            "u2",
            "tenant-a",
            NotificationEvent.RELEASE_BLOCKED,
            NotificationChannel.EMAIL,
            "ops@company.com",
        )
        subs = mgr.get_subscribers(NotificationEvent.RELEASE_BLOCKED, "tenant-a")
        assert len(subs) == 2

    def test_severity_threshold_filtering(self) -> None:
        from app.core.notifications.manager import NotificationManager

        mgr = NotificationManager()
        assert mgr._severity_meets_threshold("critical", "high") is True
        assert mgr._severity_meets_threshold("low", "critical") is False
        assert mgr._severity_meets_threshold("high", "high") is True

    def test_delete_preference(self) -> None:
        from app.core.notifications.manager import NotificationManager
        from app.core.notifications.preferences import NotificationChannel, NotificationEvent

        mgr = NotificationManager()
        pref = mgr.set_preference(
            "u1", "t1", NotificationEvent.WEEKLY_DIGEST, NotificationChannel.EMAIL, "a@b.com"
        )
        deleted = mgr.delete_preference(pref.pref_id, "u1")
        assert deleted is True
        assert len(mgr.get_preferences("u1")) == 0

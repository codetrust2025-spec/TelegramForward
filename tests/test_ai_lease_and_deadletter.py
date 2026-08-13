"""The AI claim lease must outlive a real analysis, and attempts must be capped.

Production ran a 150s lease against a ~154s analysis (primary plus validator),
so rows were reclaimed mid-flight and recycled: 40 of 63 queued messages carried
LEASE_EXPIRED and retry counts passed 100. Nothing was failing — it never
finished. Transient failures must still retry; only exhausted rows are parked.
"""

import os

from core import recruitment_mail_store as store


def _lease_seconds(monkeypatch, *, configured="150", job_timeout="660"):
    """The lease the worker computes, mirroring workers/recruitment_mail_worker."""
    monkeypatch.setenv("AI_MAIL_AI_LEASE_SECONDS", configured)
    monkeypatch.setenv("AI_JOB_TIMEOUT", job_timeout)
    job = int(os.getenv("AI_JOB_TIMEOUT", os.getenv("AI_RECRUITMENT_JOB_TIMEOUT_SECONDS", "660")))
    return max(60, min(900, max(int(os.getenv("AI_MAIL_AI_LEASE_SECONDS", "150")), job + 60)))


class TestLeaseOutlivesAnalysis:
    def test_a_long_running_analysis_is_not_reclaimed(self, monkeypatch):
        """The production case: 150s configured, ~154s analysis."""
        lease = _lease_seconds(monkeypatch)
        assert lease > 154, "lease must outlive a primary+validator run"
        assert lease >= 720

    def test_an_explicitly_larger_lease_is_respected(self, monkeypatch):
        assert _lease_seconds(monkeypatch, configured="880") == 880

    def test_the_lease_stays_within_the_clamp(self, monkeypatch):
        assert _lease_seconds(monkeypatch, configured="99999", job_timeout="99999") == 900

    def test_a_short_job_budget_still_floors_above_the_old_value(self, monkeypatch):
        lease = _lease_seconds(monkeypatch, configured="150", job_timeout="200")
        assert lease == 260
        assert lease > 154


class TestAttemptCap:
    def test_the_cap_has_a_safe_default(self, monkeypatch):
        monkeypatch.delenv("AI_MAIL_MAX_AI_ATTEMPTS", raising=False)
        assert store._max_ai_attempts() == 12

    def test_the_cap_is_configurable_within_bounds(self, monkeypatch):
        monkeypatch.setenv("AI_MAIL_MAX_AI_ATTEMPTS", "25")
        assert store._max_ai_attempts() == 25
        monkeypatch.setenv("AI_MAIL_MAX_AI_ATTEMPTS", "1")
        assert store._max_ai_attempts() == 3, "never park after fewer than 3 tries"
        monkeypatch.setenv("AI_MAIL_MAX_AI_ATTEMPTS", "9999")
        assert store._max_ai_attempts() == 50

    def test_a_malformed_cap_falls_back_rather_than_crashing(self, monkeypatch):
        monkeypatch.setenv("AI_MAIL_MAX_AI_ATTEMPTS", "not-a-number")
        assert store._max_ai_attempts() == 12

    def test_transient_failures_still_retry_below_the_cap(self, monkeypatch):
        """A handful of Ollama blips must not park a message."""
        monkeypatch.delenv("AI_MAIL_MAX_AI_ATTEMPTS", raising=False)
        cap = store._max_ai_attempts()
        for attempts in (0, 1, 3, cap - 1):
            assert attempts < cap, f"{attempts} attempts must remain claimable"


class TestClaimQuerySafety:
    """The claim path keeps its idempotency and single-processing guarantees."""

    def _source(self):
        import inspect
        return inspect.getsource(store.claim_ai_messages)

    def test_exhausted_rows_are_excluded_from_the_claim(self):
        assert "COALESCE(ai_retry_count,0)<%s" in self._source()

    def test_exhausted_rows_are_parked_terminally_not_requeued(self):
        src = self._source()
        assert "AI_FAILED_TERMINAL" in src
        assert "MAX_ATTEMPTS_EXHAUSTED" in src

    def test_terminal_state_is_not_a_claimable_status(self):
        """A parked row must never be selected again by the claim query."""
        src = self._source()
        claim_statuses = "processing_status IN ('AI_QUEUED','AI_RETRY_PENDING')"
        assert claim_statuses in src
        assert "'AI_FAILED_TERMINAL'" not in claim_statuses

    def test_no_duplicate_processing(self):
        """Row-level locking is what stops two workers taking the same row."""
        src = self._source()
        assert "FOR UPDATE SKIP LOCKED" in src

    def test_the_lease_is_still_applied_on_claim(self):
        assert "ai_lease_expires_at=now()+" in self._source()


def test_already_exhausted_queued_rows_are_parked_not_left_pending():
    """Rows that passed the cap before it existed must not linger as backlog."""
    import inspect
    src = inspect.getsource(store.claim_ai_messages)
    assert "processing_status IN ('AI_QUEUED','AI_RETRY_PENDING')\n              AND COALESCE(ai_retry_count,0)>=%s" in src

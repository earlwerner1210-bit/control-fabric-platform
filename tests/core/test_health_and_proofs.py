from __future__ import annotations


class TestCustomerHealthScorer:
    def test_scores_default_tenant(self) -> None:
        from app.core.health_scoring.scorer import CustomerHealthScorer

        scorer = CustomerHealthScorer()
        score = scorer.score_tenant("test-tenant-health")
        assert 0 <= score.overall_score <= 100
        assert score.grade in ["A", "B", "C", "D", "F"]
        assert score.risk_level in ["healthy", "at_risk", "churn_risk"]
        assert len(score.components) == 5
        assert len(score.recommendations) >= 1

    def test_components_sum_to_overall(self) -> None:
        from app.core.health_scoring.scorer import CustomerHealthScorer

        scorer = CustomerHealthScorer()
        score = scorer.score_tenant("test-sum")
        component_sum = sum(c.score for c in score.components)
        assert abs(component_sum - score.overall_score) < 0.5

    def test_grade_thresholds_correct(self) -> None:
        from app.core.health_scoring.scorer import CustomerHealthScorer

        scorer = CustomerHealthScorer()
        cases = [(95, "A"), (80, "B"), (65, "C"), (45, "D"), (30, "F")]
        for score_val, expected_grade in cases:
            grade = next(g for t, g in scorer.GRADE_THRESHOLDS if score_val >= t)
            assert grade == expected_grade, (
                f"Score {score_val} should be grade {expected_grade}, got {grade}"
            )

    def test_score_all_tenants(self) -> None:
        from app.core.health_scoring.scorer import CustomerHealthScorer

        scorer = CustomerHealthScorer()
        scores = scorer.score_all_tenants()
        assert isinstance(scores, list)
        assert len(scores) >= 1

    def test_at_risk_filter(self) -> None:
        from app.core.health_scoring.scorer import CustomerHealthScorer

        scorer = CustomerHealthScorer()
        at_risk = scorer.get_at_risk_tenants()
        assert all(s.risk_level != "healthy" for s in at_risk)

    def test_history_tracked(self) -> None:
        from app.core.health_scoring.scorer import CustomerHealthScorer

        scorer = CustomerHealthScorer()
        scorer.score_tenant("history-tenant")
        scorer.score_tenant("history-tenant")
        assert len(scorer._history.get("history-tenant", [])) == 2


class TestCompetitiveProofs:
    def test_proof_not_workflow_runs(self) -> None:
        from demos.proof_not_workflow import run

        run()  # raises AssertionError if proof fails

    def test_proof_not_ai_governance_runs(self) -> None:
        from demos.proof_not_ai_governance import run

        run()

    def test_proof_not_audit_logging_runs(self) -> None:
        from demos.proof_not_audit_logging import run

        run()

    def test_proof_semantic_gap_runs(self) -> None:
        from demos.proof_semantic_gap_detection import run

        run()

    def test_all_proofs_pass(self) -> None:
        """Run the full proof suite and confirm all pass."""
        from demos.run_all_proofs import main

        result = main()
        assert result == 0, "One or more competitive proofs failed"

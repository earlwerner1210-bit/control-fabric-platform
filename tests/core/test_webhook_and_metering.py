from __future__ import annotations

import hashlib
import hmac
import json


def make_sig(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestWebhookSignatureVerifier:
    def test_github_valid_signature(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookSignatureVerifier

        v = WebhookSignatureVerifier()
        payload = b'{"action":"completed"}'
        secret = "test-secret"
        assert v.verify_github(payload, make_sig(payload, secret), secret) is True

    def test_github_invalid_signature_rejected(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookSignatureVerifier

        v = WebhookSignatureVerifier()
        assert v.verify_github(b"payload", "sha256=wrong", "secret") is False

    def test_generic_valid_signature(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookSignatureVerifier

        v = WebhookSignatureVerifier()
        payload = b'{"event":"test"}'
        secret = "my-secret"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert v.verify_generic(payload, sig, secret) is True

    def test_no_secret_passes_generic(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookSignatureVerifier

        v = WebhookSignatureVerifier()
        assert v.verify_generic(b"payload", "", "") is True

    def test_replay_rejects_old_timestamp(self) -> None:
        import time

        from app.core.connectors.webhook_receiver import WebhookSignatureVerifier

        v = WebhookSignatureVerifier()
        old = str(int(time.time()) - 400)
        assert v.check_replay(old) is False

    def test_replay_accepts_fresh_timestamp(self) -> None:
        import time

        from app.core.connectors.webhook_receiver import WebhookSignatureVerifier

        v = WebhookSignatureVerifier()
        assert v.check_replay(str(int(time.time()))) is True


class TestWebhookConverter:
    def test_converts_github_workflow_run(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookToArtefactConverter

        c = WebhookToArtefactConverter()
        payload = {
            "workflow_run": {
                "id": 1,
                "run_number": 42,
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "head_branch": "main",
                "head_sha": "abc123",
            },
            "sender": {"login": "engineer"},
            "repository": {"full_name": "org/repo"},
        }
        artefacts = c.convert_github("workflow_run", payload)
        assert len(artefacts) == 1
        obj = json.loads(artefacts[0].raw_content)
        assert obj["evidence_type"] == "ci_result"
        assert obj["conclusion"] == "success"

    def test_converts_jira_change_request(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookToArtefactConverter

        c = WebhookToArtefactConverter()
        payload = {
            "webhookEvent": "jira:issue_updated",
            "issue": {
                "key": "CR-123",
                "fields": {
                    "summary": "Release API v2",
                    "issuetype": {"name": "Change Request"},
                    "status": {"name": "Approved"},
                    "assignee": {"displayName": "Alice"},
                },
            },
        }
        artefacts = c.convert_jira("jira:issue_updated", payload)
        assert len(artefacts) == 1
        obj = json.loads(artefacts[0].raw_content)
        assert obj["evidence_type"] == "change_request"
        assert obj["issue_key"] == "CR-123"

    def test_converts_servicenow_change(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookToArtefactConverter

        c = WebhookToArtefactConverter()
        payload = {
            "table": "change_request",
            "record": {
                "number": "CHG001",
                "short_description": "Deploy v2",
                "state": "3",
                "approval": "approved",
            },
        }
        artefacts = c.convert_servicenow("change_request.updated", payload)
        assert len(artefacts) == 1
        assert json.loads(artefacts[0].raw_content)["evidence_type"] == "change_request"

    def test_converts_ado_build(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookToArtefactConverter

        c = WebhookToArtefactConverter()
        payload = {
            "eventType": "build.complete",
            "resource": {
                "id": 999,
                "buildNumber": "20260101.1",
                "result": "succeeded",
                "definition": {"name": "CI Pipeline"},
            },
        }
        artefacts = c.convert_azure_devops("build.complete", payload)
        assert len(artefacts) == 1
        assert json.loads(artefacts[0].raw_content)["evidence_type"] == "ci_result"


class TestWebhookReceiver:
    def test_no_secret_accepts_all(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookReceiver

        r = WebhookReceiver()
        r._secrets["github"] = ""
        payload = json.dumps(
            {
                "workflow_run": {
                    "id": 1,
                    "run_number": 1,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "head_branch": "main",
                    "head_sha": "abc",
                },
                "sender": {"login": "user"},
                "repository": {"full_name": "org/repo"},
            }
        ).encode()
        result = r.receive(
            "github", "workflow_run", payload, auto_ingest=False, auto_reconcile=False
        )
        assert result.accepted is True

    def test_wrong_signature_rejected(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookReceiver

        r = WebhookReceiver()
        r._secrets["github"] = "real-secret"
        result = r.receive(
            "github", "push", b'{"test":1}', signature="sha256=wrong", auto_ingest=False
        )
        assert result.accepted is False
        assert result.rejection_reason == "signature_verification_failed"

    def test_valid_github_signature_accepted(self) -> None:
        from app.core.connectors.webhook_receiver import WebhookReceiver

        r = WebhookReceiver()
        secret = "test-secret"
        r._secrets["github"] = secret
        payload = json.dumps(
            {
                "workflow_run": {
                    "id": 1,
                    "run_number": 1,
                    "name": "CI",
                    "status": "completed",
                    "conclusion": "success",
                    "head_branch": "main",
                    "head_sha": "abc",
                },
                "sender": {"login": "user"},
                "repository": {"full_name": "org/repo"},
            }
        ).encode()
        sig = make_sig(payload, secret)
        result = r.receive(
            "github",
            "workflow_run",
            payload,
            signature=sig,
            auto_ingest=False,
            auto_reconcile=False,
        )
        assert result.accepted is True


class TestMeteringEngine:
    def test_records_events_per_tenant(self) -> None:
        from app.core.metering.meter import MeteringEngine

        e = MeteringEngine()
        e.record("gate_submission", "tenant-a", 3)
        e.record("gate_block", "tenant-a", 1)
        assert e.get_usage("tenant-a")["gate_submission"] == 3
        assert e.get_usage("tenant-a")["gate_block"] == 1

    def test_tenant_isolation(self) -> None:
        from app.core.metering.meter import MeteringEngine

        e = MeteringEngine()
        e.record("gate_submission", "t1", 5)
        e.record("gate_submission", "t2", 3)
        assert e.get_usage("t1").get("gate_submission") == 5
        assert e.get_usage("t2").get("gate_submission") == 3

    def test_summary_calculates_cost(self) -> None:
        from app.core.metering.meter import MeteringEngine

        e = MeteringEngine()
        e.record("gate_submission", "billing-t", 100)
        e.record("reconciliation_run", "billing-t", 10)
        s = e.get_summary("billing-t")
        assert s.estimated_cost_gbp > 0
        assert s.total_events == 110
        assert s.billable_units == 110

    def test_stripe_not_configured_graceful(self) -> None:
        from app.core.metering.meter import MeteringEngine

        e = MeteringEngine()
        e.record("gate_submission", "t-x")
        result = e.report_to_stripe("t-x")
        assert result["reported"] is False
        assert "Stripe not configured" in result["reason"]

    def test_get_all_tenants(self) -> None:
        from app.core.metering.meter import MeteringEngine

        e = MeteringEngine()
        e.record("gate_submission", "alpha")
        e.record("gate_submission", "beta")
        tenants = e.get_all_tenants()
        assert "alpha" in tenants
        assert "beta" in tenants

    def test_record_never_raises(self) -> None:
        from app.core.metering.meter import MeteringEngine

        e = MeteringEngine()
        # Should not raise even with weird inputs
        e.record("unknown_event_type", "tenant", -1)
        e.record("", "", 0)

from opspilot_mcp.aws.tools import (
    scan_idle_resources,
    inspect_resource,
    estimate_resource_cost,
    draft_teardown_plan,
)


def test_payments_api_scan():
    result = scan_idle_resources(
        "payments-api"
    )

    assert result["resource_count"] >= 2
    assert result["changes_executed"] is False
    assert result["requires_human_review"] is True

    resources = result["resources"]

    types = {
        r["resource_type"]
        for r in resources
    }

    assert "ebs_volume" in types
    assert "load_balancer" in types


def test_demo_alb_detected():
    result = inspect_resource(
        "opspilot-demo-alb"
    )

    assert result["found"] is True
    assert result["changes_executed"] is False

    alb = result["resource"]

    assert alb["service"] == "payments-api"
    assert alb["healthy_targets"] == 0
    assert alb["cleanup_candidate"] is True
    assert alb["requires_human_review"] is True


def test_demo_alb_cost():
    result = estimate_resource_cost(
        "opspilot-demo-alb"
    )

    assert result["found"] is True
    assert result["monthly_estimate"] is not None
    assert result["monthly_estimate"] > 0
    assert result["is_estimate"] is True
    assert result["changes_executed"] is False


def test_teardown_is_plan_only():
    result = draft_teardown_plan(
        "opspilot-demo-alb"
    )

    assert result["found"] is True

    assert (
        result["status"]
        == "REVIEW_REQUIRED"
    )

    assert (
        result["requires_human_review"]
        is True
    )

    assert result["executed"] is False

    assert (
        result["changes_executed"]
        is False
    )

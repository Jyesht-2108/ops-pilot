from mcp.aws.resources import (
    scan_idle_resources as _scan_idle_resources,
)


# =========================================================
# TOOL 1 — SCAN IDLE RESOURCES
# =========================================================

def scan_idle_resources(service=None):
    """
    Scan OpsPilot demo AWS resources for cleanup candidates.

    Optional:
        service="payments-api"

    This tool is READ-ONLY.
    """

    return _scan_idle_resources(
        service=service
    )


# =========================================================
# TOOL 2 — INSPECT RESOURCE
# =========================================================

def inspect_resource(resource_id):
    """
    Return evidence for one detected cleanup candidate.

    This currently searches the Cloud Cost Janitor findings
    rather than mutating or modifying the AWS resource.
    """

    result = _scan_idle_resources()

    for resource in result.get(
        "resources",
        []
    ):

        if (
            resource.get("resource_id")
            == resource_id
            or resource.get("resource_arn")
            == resource_id
        ):

            return {
                "found": True,
                "resource": resource,
                "changes_executed": False,
            }

    return {
        "found": False,
        "resource_id": resource_id,
        "message":
            "Resource was not found among current "
            "OpsPilot cleanup candidates.",
        "changes_executed": False,
    }


# =========================================================
# TOOL 3 — ESTIMATE RESOURCE COST
# =========================================================

def estimate_resource_cost(resource_id):
    """
    Return the monthly cost estimate already calculated
    for a detected resource.
    """

    inspection = inspect_resource(
        resource_id
    )

    if not inspection["found"]:

        return {
            "found": False,
            "resource_id": resource_id,
            "monthly_estimate": None,
            "changes_executed": False,
        }

    resource = inspection[
        "resource"
    ]

    return {
        "found": True,

        "resource_id":
            resource.get(
                "resource_id"
            ),

        "resource_type":
            resource.get(
                "resource_type"
            ),

        "service":
            resource.get(
                "service"
            ),

        "monthly_estimate":
            resource.get(
                "monthly_estimate"
            ),

        "currency":
            resource.get(
                "currency",
                "USD"
            ),

        "is_estimate":
            resource.get(
                "is_estimate",
                True
            ),

        "estimate_method":
            resource.get(
                "estimate_method"
            ),

        "changes_executed":
            False,
    }


# =========================================================
# TOOL 4 — DRAFT TEARDOWN PLAN
# =========================================================

def draft_teardown_plan(
    resource_id
):
    """
    Produce a human-reviewable teardown plan.

    IMPORTANT:
    This function NEVER deletes, stops, detaches,
    terminates, or modifies AWS infrastructure.
    """

    inspection = inspect_resource(
        resource_id
    )

    if not inspection["found"]:

        return {
            "found": False,
            "resource_id": resource_id,
            "status":
                "RESOURCE_NOT_FOUND",
            "executed": False,
        }

    resource = inspection[
        "resource"
    ]

    resource_type = resource.get(
        "resource_type"
    )

    # ---------------------------------------------
    # Resource-specific proposed steps
    # ---------------------------------------------

    if resource_type == "ebs_volume":

        proposed_steps = [
            (
                "Confirm the volume is still "
                "unattached."
            ),
            (
                "Confirm the service owner no "
                "longer requires the volume."
            ),
            (
                "Review whether a snapshot or "
                "backup is required."
            ),
            (
                "Delete the EBS volume only "
                "after explicit human approval."
            ),
        ]

    elif resource_type == "ec2_instance":

        proposed_steps = [
            (
                "Review recent utilization and "
                "service ownership."
            ),
            (
                "Confirm no active incident "
                "depends on the instance."
            ),
            (
                "Consider stopping the instance "
                "before termination."
            ),
            (
                "Terminate only after explicit "
                "human approval."
            ),
        ]

    elif resource_type == "load_balancer":

        proposed_steps = [
            (
                "Confirm the load balancer is "
                "still associated with the "
                "expected service."
            ),
            (
                "Review target groups, listeners, "
                "traffic and target health."
            ),
            (
                "Check whether an open support "
                "incident references the service."
            ),
            (
                "Remove the load balancer only "
                "after explicit human approval."
            ),
        ]

    else:

        proposed_steps = [
            (
                "Review the resource manually."
            ),
            (
                "Take no action without human "
                "approval."
            ),
        ]

    # ---------------------------------------------
    # Result
    # ---------------------------------------------

    return {
        "found": True,

        "status":
            "REVIEW_REQUIRED",

        "resource_id":
            resource.get(
                "resource_id"
            ),

        "resource_type":
            resource_type,

        "service":
            resource.get(
                "service"
            ),

        "signals":
            resource.get(
                "signals",
                []
            ),

        "estimated_monthly_savings":
            resource.get(
                "monthly_estimate"
            ),

        "currency":
            resource.get(
                "currency",
                "USD"
            ),

        "proposed_steps":
            proposed_steps,

        "requires_human_review":
            True,

        "executed":
            False,

        "changes_executed":
            False,
    }
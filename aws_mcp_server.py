from fastmcp import FastMCP

from opspilot_mcp.aws.tools import (
    scan_idle_resources as aws_scan_idle_resources,
    inspect_resource as aws_inspect_resource,
    estimate_resource_cost as aws_estimate_resource_cost,
    draft_teardown_plan as aws_draft_teardown_plan,
)


mcp = FastMCP("OpsPilot AWS Cloud Cost Janitor")


@mcp.tool
def scan_idle_resources(service: str | None = None) -> dict:
    """
    Scan OpsPilot demo AWS infrastructure for idle or
    orphaned cleanup candidates.

    Optionally filter by service, for example:
    payments-api

    READ-ONLY.
    No AWS infrastructure is modified.
    """

    return aws_scan_idle_resources(
        service=service
    )


@mcp.tool
def inspect_resource(resource_id: str) -> dict:
    """
    Inspect a detected AWS cleanup candidate.

    Returns operational evidence, utilization signals,
    service correlation and estimated cost.

    READ-ONLY.
    """

    return aws_inspect_resource(
        resource_id
    )


@mcp.tool
def estimate_resource_cost(resource_id: str) -> dict:
    """
    Return OpsPilot's estimated monthly cost for a
    detected AWS resource.

    The returned value is explicitly labelled as an
    estimate.

    READ-ONLY.
    """

    return aws_estimate_resource_cost(
        resource_id
    )


@mcp.tool
def draft_teardown_plan(resource_id: str) -> dict:
    """
    Draft a human-reviewable teardown plan.

    This tool NEVER deletes, stops, terminates, detaches
    or modifies AWS infrastructure.

    Every consequential action requires human review.
    """

    return aws_draft_teardown_plan(
        resource_id
    )


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=8765,
    )
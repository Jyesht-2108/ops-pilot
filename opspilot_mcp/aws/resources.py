from datetime import datetime, timezone, timedelta

from opspilot_mcp.aws.client import (
    get_ec2_client,
    get_cloudwatch_client,
    get_elbv2_client,
)

from opspilot_mcp.aws.cost import (
    estimate_ebs_monthly_cost,
    estimate_alb_monthly_cost,
)


# =========================================================
# COMMON HELPERS
# =========================================================

def tags_to_dict(tags):
    """
    Convert AWS tags:

    [{"Key": "Name", "Value": "demo"}]

    into:

    {"Name": "demo"}
    """

    return {
        tag["Key"]: tag["Value"]
        for tag in (tags or [])
    }


def calculate_age_days(created_at):
    """
    Calculate how many days old an AWS resource is.
    """

    now = datetime.now(timezone.utc)

    return (now - created_at).days


# =========================================================
# EBS SCANNER
# =========================================================

def scan_orphaned_ebs_volumes():
    """
    Find EBS volumes that are:

    - tagged OpsPilotDemo=true
    - state == available
    - not attached to any EC2 instance

    These are cleanup candidates only.

    OpsPilot NEVER automatically deletes them.
    """

    ec2 = get_ec2_client()

    response = ec2.describe_volumes()

    candidates = []

    for volume in response.get("Volumes", []):

        state = volume.get("State")

        attachments = volume.get(
            "Attachments",
            []
        )

        tags = tags_to_dict(
            volume.get(
                "Tags",
                []
            )
        )

        # -----------------------------------------
        # Safety: only inspect demo resources
        # -----------------------------------------

        if tags.get("OpsPilotDemo") != "true":
            continue

        is_orphaned = (
            state == "available"
            and len(attachments) == 0
        )

        if not is_orphaned:
            continue

        # -----------------------------------------
        # Estimate monthly EBS cost
        # -----------------------------------------

        cost = estimate_ebs_monthly_cost(
            size_gb=volume["Size"],
            volume_type=volume["VolumeType"],
            iops=volume.get("Iops"),
            throughput=volume.get("Throughput"),
        )

        candidates.append(
            {
                "resource_id":
                    volume["VolumeId"],

                "resource_type":
                    "ebs_volume",

                "service":
                    tags.get("OpsPilotService"),

                "name":
                    tags.get("Name"),

                "state":
                    state,

                "size_gb":
                    volume["Size"],

                "volume_type":
                    volume["VolumeType"],

                "age_days":
                    calculate_age_days(
                        volume["CreateTime"]
                    ),

                # Detection evidence
                "signals": [
                    "volume_state_available",
                    "no_instance_attachment",
                ],

                # Cost evidence
                "monthly_estimate":
                    cost["monthly_estimate"],

                "currency":
                    cost["currency"],

                "is_estimate":
                    cost["is_estimate"],

                "estimate_method":
                    cost["estimate_method"],

                # Decision
                "cleanup_candidate":
                    True,

                "requires_human_review":
                    True,
            }
        )

    return candidates


# =========================================================
# EC2 CLOUDWATCH CPU HELPER
# =========================================================

def get_average_cpu(
    instance_id,
    hours=6,
):
    """
    Get average CPU utilization for an EC2 instance.

    Returns:
        float -> average CPU percentage
        None -> CloudWatch returned no datapoints

    IMPORTANT:
    No CloudWatch data does NOT mean 0% CPU.
    """

    cloudwatch = get_cloudwatch_client()

    end_time = datetime.now(
        timezone.utc
    )

    start_time = (
        end_time
        - timedelta(
            hours=hours
        )
    )

    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/EC2",

        MetricName="CPUUtilization",

        Dimensions=[
            {
                "Name": "InstanceId",
                "Value": instance_id,
            }
        ],

        StartTime=start_time,
        EndTime=end_time,

        Period=300,

        Statistics=[
            "Average"
        ],
    )

    datapoints = response.get(
        "Datapoints",
        []
    )

    if not datapoints:
        return None

    averages = [
        point["Average"]
        for point in datapoints
        if "Average" in point
    ]

    if not averages:
        return None

    average_cpu = (
        sum(averages)
        / len(averages)
    )

    return average_cpu


# =========================================================
# EC2 IDLE SCANNER
# =========================================================

def scan_idle_ec2_instances(
    cpu_threshold=5.0,
    observation_hours=6,
):
    """
    Find idle EC2 instances.

    Hackathon MVP rule:

    - Instance must be running
    - Instance must have OpsPilotDemo=true
    - CloudWatch CPU data must exist
    - Average CPU must be below threshold

    OpsPilot does NOT stop or terminate instances.
    """

    ec2 = get_ec2_client()

    response = ec2.describe_instances(
        Filters=[
            {
                "Name":
                    "instance-state-name",

                "Values": [
                    "running"
                ],
            },
            {
                "Name":
                    "tag:OpsPilotDemo",

                "Values": [
                    "true"
                ],
            },
        ]
    )

    candidates = []

    for reservation in response.get(
        "Reservations",
        []
    ):

        for instance in reservation.get(
            "Instances",
            []
        ):

            instance_id = (
                instance["InstanceId"]
            )

            tags = tags_to_dict(
                instance.get(
                    "Tags",
                    []
                )
            )

            avg_cpu = get_average_cpu(
                instance_id=instance_id,
                hours=observation_hours,
            )

            # No CloudWatch evidence means
            # we do not classify it as idle.
            if avg_cpu is None:
                continue

            is_idle = (
                avg_cpu
                < cpu_threshold
            )

            if not is_idle:
                continue

            candidates.append(
                {
                    "resource_id":
                        instance_id,

                    "resource_type":
                        "ec2_instance",

                    "service":
                        tags.get(
                            "OpsPilotService"
                        ),

                    "name":
                        tags.get(
                            "Name"
                        ),

                    "state":
                        instance[
                            "State"
                        ][
                            "Name"
                        ],

                    "instance_type":
                        instance[
                            "InstanceType"
                        ],

                    "availability_zone":
                        instance[
                            "Placement"
                        ][
                            "AvailabilityZone"
                        ],

                    "age_days":
                        calculate_age_days(
                            instance[
                                "LaunchTime"
                            ]
                        ),

                    "average_cpu_percent":
                        round(
                            avg_cpu,
                            2,
                        ),

                    "observation_hours":
                        observation_hours,

                    "cpu_threshold_percent":
                        cpu_threshold,

                    "signals": [
                        "instance_running",

                        (
                            "average_cpu_"
                            f"{round(avg_cpu, 2)}%"
                        ),

                        (
                            "cpu_below_threshold_"
                            f"{cpu_threshold}%"
                        ),
                    ],

                    "cleanup_candidate":
                        True,

                    "requires_human_review":
                        True,
                }
            )

    return candidates


# =========================================================
# ALB TAG HELPER
# =========================================================

def get_alb_tags(load_balancer_arn):
    """
    Get tags attached to an Application Load Balancer.
    """

    elbv2 = get_elbv2_client()

    response = elbv2.describe_tags(
        ResourceArns=[
            load_balancer_arn
        ]
    )

    descriptions = response.get(
        "TagDescriptions",
        []
    )

    if not descriptions:
        return {}

    return tags_to_dict(
        descriptions[0].get(
            "Tags",
            []
        )
    )


# =========================================================
# ALB CLOUDWATCH NAME HELPER
# =========================================================

def get_alb_cloudwatch_name(
    load_balancer_arn
):
    """
    Convert ALB ARN into the CloudWatch LoadBalancer
    dimension.

    Example:

    arn:aws:elasticloadbalancing:...:
    loadbalancer/app/opspilot-demo-alb/abc

    becomes:

    app/opspilot-demo-alb/abc
    """

    marker = "loadbalancer/"

    if marker not in load_balancer_arn:
        return None

    return load_balancer_arn.split(
        marker,
        1
    )[1]


# =========================================================
# ALB REQUEST COUNT HELPER
# =========================================================

def get_alb_request_count(
    load_balancer_arn,
    hours=6,
):
    """
    Get total requests observed for an ALB.

    Returns:

    {
        "requests": 10,
        "datapoints_found": True
    }

    If no CloudWatch datapoints exist:

    {
        "requests": 0,
        "datapoints_found": False
    }
    """

    cloudwatch = get_cloudwatch_client()

    cloudwatch_name = (
        get_alb_cloudwatch_name(
            load_balancer_arn
        )
    )

    if not cloudwatch_name:
        return {
            "requests": None,
            "datapoints_found": False,
        }

    end_time = datetime.now(
        timezone.utc
    )

    start_time = (
        end_time
        - timedelta(
            hours=hours
        )
    )

    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/ApplicationELB",

        MetricName="RequestCount",

        Dimensions=[
            {
                "Name": "LoadBalancer",
                "Value": cloudwatch_name,
            }
        ],

        StartTime=start_time,
        EndTime=end_time,

        Period=300,

        Statistics=[
            "Sum"
        ],
    )

    datapoints = response.get(
        "Datapoints",
        []
    )

    if not datapoints:
        return {
            "requests": 0,
            "datapoints_found": False,
        }

    total_requests = sum(
        point.get(
            "Sum",
            0
        )
        for point in datapoints
    )

    return {
        "requests":
            int(total_requests),

        "datapoints_found":
            True,
    }


# =========================================================
# ALB TARGET HEALTH HELPER
# =========================================================

def get_alb_target_health(
    load_balancer_arn
):
    """
    Inspect all target groups attached to an ALB.

    Returns:
    - target group count
    - total target count
    - healthy target count
    - unhealthy target count
    """

    elbv2 = get_elbv2_client()

    response = (
        elbv2.describe_target_groups(
            LoadBalancerArn=(
                load_balancer_arn
            )
        )
    )

    target_groups = response.get(
        "TargetGroups",
        []
    )

    total_targets = 0
    healthy_targets = 0
    unhealthy_targets = 0

    target_details = []

    for target_group in target_groups:

        target_group_arn = (
            target_group[
                "TargetGroupArn"
            ]
        )

        health_response = (
            elbv2.describe_target_health(
                TargetGroupArn=(
                    target_group_arn
                )
            )
        )

        descriptions = (
            health_response.get(
                "TargetHealthDescriptions",
                []
            )
        )

        for description in descriptions:

            total_targets += 1

            target = description.get(
                "Target",
                {}
            )

            health = description.get(
                "TargetHealth",
                {}
            )

            state = health.get(
                "State",
                "unknown"
            )

            if state == "healthy":

                healthy_targets += 1

            else:

                unhealthy_targets += 1

            target_details.append(
                {
                    "target_id":
                        target.get(
                            "Id"
                        ),

                    "state":
                        state,

                    "reason":
                        health.get(
                            "Reason"
                        ),
                }
            )

    return {
        "target_group_count":
            len(target_groups),

        "total_targets":
            total_targets,

        "healthy_targets":
            healthy_targets,

        "unhealthy_targets":
            unhealthy_targets,

        "targets":
            target_details,
    }


# =========================================================
# APPLICATION LOAD BALANCER SCANNER
# =========================================================

def scan_idle_load_balancers(
    request_threshold=5,
    observation_hours=6,
):
    """
    Find Application Load Balancers that appear
    idle or forgotten.

    Hackathon MVP:

    - ALB must have OpsPilotDemo=true

    Candidate if either:

    - near-zero traffic
    OR
    - zero healthy targets

    OpsPilot NEVER deletes the ALB automatically.
    """

    elbv2 = get_elbv2_client()

    response = (
        elbv2.describe_load_balancers()
    )

    candidates = []

    for load_balancer in response.get(
        "LoadBalancers",
        []
    ):

        # Only Application Load Balancers
        if load_balancer.get(
            "Type"
        ) != "application":

            continue

        arn = (
            load_balancer[
                "LoadBalancerArn"
            ]
        )

        # -----------------------------------------
        # Tags
        # -----------------------------------------

        tags = get_alb_tags(
            arn
        )

        # Only scan OpsPilot demo resources
        if tags.get(
            "OpsPilotDemo"
        ) != "true":

            continue

        # -----------------------------------------
        # Traffic evidence
        # -----------------------------------------

        traffic = (
            get_alb_request_count(
                arn,
                hours=observation_hours,
            )
        )

        # -----------------------------------------
        # Target health evidence
        # -----------------------------------------

        health = (
            get_alb_target_health(
                arn
            )
        )

        request_count = (
            traffic[
                "requests"
            ]
        )

        datapoints_found = (
            traffic[
                "datapoints_found"
            ]
        )

        healthy_targets = (
            health[
                "healthy_targets"
            ]
        )

        # -----------------------------------------
        # Detection rules
        # -----------------------------------------

        near_zero_traffic = (
            request_count is not None
            and request_count
            <= request_threshold
        )

        zero_healthy_targets = (
            healthy_targets == 0
        )

        cleanup_candidate = (
            near_zero_traffic
            or zero_healthy_targets
        )

        if not cleanup_candidate:
            continue

        # -----------------------------------------
        # Cost estimate
        # -----------------------------------------

        cost = estimate_alb_monthly_cost()

        # -----------------------------------------
        # Evidence signals
        # -----------------------------------------

        signals = []

        if near_zero_traffic:

            if datapoints_found:

                signals.append(
                    (
                        "near_zero_traffic_"
                        f"{request_count}_requests"
                    )
                )

            else:

                signals.append(
                    "no_requestcount_datapoints_observed"
                )

        if zero_healthy_targets:

            signals.append(
                "zero_healthy_targets"
            )

        if (
            health[
                "target_group_count"
            ]
            == 0
        ):

            signals.append(
                "no_target_groups"
            )

        # -----------------------------------------
        # Candidate result
        # -----------------------------------------

        candidates.append(
            {
                "resource_id":
                    load_balancer[
                        "LoadBalancerName"
                    ],

                "resource_arn":
                    arn,

                "resource_type":
                    "load_balancer",

                "service":
                    tags.get(
                        "OpsPilotService"
                    ),

                "name":
                    tags.get(
                        "Name",
                        load_balancer[
                            "LoadBalancerName"
                        ]
                    ),

                "state":
                    load_balancer.get(
                        "State",
                        {}
                    ).get(
                        "Code"
                    ),

                "scheme":
                    load_balancer.get(
                        "Scheme"
                    ),

                "dns_name":
                    load_balancer.get(
                        "DNSName"
                    ),

                "age_days":
                    calculate_age_days(
                        load_balancer[
                            "CreatedTime"
                        ]
                    ),

                "request_count":
                    request_count,

                "request_metric_datapoints":
                    datapoints_found,

                "observation_hours":
                    observation_hours,

                "request_threshold":
                    request_threshold,

                "target_group_count":
                    health[
                        "target_group_count"
                    ],

                "total_targets":
                    health[
                        "total_targets"
                    ],

                "healthy_targets":
                    health[
                        "healthy_targets"
                    ],

                "unhealthy_targets":
                    health[
                        "unhealthy_targets"
                    ],

                "targets":
                    health[
                        "targets"
                    ],

                # Cost evidence
                "monthly_estimate":
                    cost["monthly_estimate"],

                "currency":
                    cost["currency"],

                "is_estimate":
                    cost["is_estimate"],

                "estimate_method":
                    cost["estimate_method"],

                "signals":
                    signals,

                "cleanup_candidate":
                    True,

                "requires_human_review":
                    True,
            }
        )

    return candidates


# =========================================================
# UNIFIED CLOUD COST JANITOR
# =========================================================

def scan_idle_resources(
    service=None
):
    """
    Run all supported OpsPilot cloud-cost scans.

    Supported:
    - EBS
    - EC2
    - Application Load Balancers

    Optionally filter by service name.

    Example:

        scan_idle_resources(
            service="payments-api"
        )

    No resources are modified or deleted.
    """

    ebs_resources = (
        scan_orphaned_ebs_volumes()
    )

    ec2_resources = (
        scan_idle_ec2_instances()
    )

    alb_resources = (
        scan_idle_load_balancers()
    )

    resources = (
        ebs_resources
        + ec2_resources
        + alb_resources
    )

    # ---------------------------------------------
    # Optional service filter
    # ---------------------------------------------

    if service is not None:

        resources = [
            resource
            for resource in resources
            if resource.get(
                "service"
            ) == service
        ]

    # ---------------------------------------------
    # Aggregate known costs
    # ---------------------------------------------

    known_costs = [
        resource.get(
            "monthly_estimate"
        )
        for resource in resources
        if resource.get(
            "monthly_estimate"
        ) is not None
    ]

    estimated_monthly_savings = round(
        sum(known_costs),
        2,
    )

    # ---------------------------------------------
    # Resource counts
    # ---------------------------------------------

    resource_counts = {
        "ebs_volume": 0,
        "ec2_instance": 0,
        "load_balancer": 0,
    }

    for resource in resources:

        resource_type = resource.get(
            "resource_type"
        )

        if resource_type in resource_counts:

            resource_counts[
                resource_type
            ] += 1

    # ---------------------------------------------
    # Structured result for Person 1 / TrueForge
    # ---------------------------------------------

    return {
        "service_filter":
            service,

        "resource_count":
            len(resources),

        "resource_counts":
            resource_counts,

        "resources":
            resources,

        "estimated_monthly_savings":
            estimated_monthly_savings,

        "currency":
            "USD",

        "is_estimate":
            True,

        "requires_human_review":
            bool(resources),

        "changes_executed":
            False,
    }


# =========================================================
# EBS REPORT
# =========================================================

def print_ebs_report():

    print()

    print(
        "OpsPilot Cloud Cost Janitor"
    )

    print(
        "==========================="
    )

    print()

    print(
        "Scanning EBS volumes..."
    )

    volumes = (
        scan_orphaned_ebs_volumes()
    )

    if not volumes:

        print(
            "No orphaned EBS volumes found."
        )

        return

    print(
        f"Found {len(volumes)} "
        f"orphaned EBS volume(s)."
    )

    for volume in volumes:

        print()

        print(
            "----------------------------"
        )

        print(
            f"Resource ID: "
            f"{volume['resource_id']}"
        )

        print(
            f"Name:        "
            f"{volume['name']}"
        )

        print(
            f"Service:     "
            f"{volume['service']}"
        )

        print(
            f"State:       "
            f"{volume['state']}"
        )

        print(
            f"Size:        "
            f"{volume['size_gb']} GB"
        )

        print(
            f"Type:        "
            f"{volume['volume_type']}"
        )

        print(
            f"Age:         "
            f"{volume['age_days']} days"
        )

        print(
            f"Est. cost:   "
            f"${volume['monthly_estimate']}"
            f"/month"
        )

        print(
            f"Currency:    "
            f"{volume['currency']}"
        )

        print(
            f"Estimate:    "
            f"{volume['is_estimate']}"
        )

        print(
            f"Method:      "
            f"{volume['estimate_method']}"
        )

        print(
            f"Candidate:   "
            f"{volume['cleanup_candidate']}"
        )

        print(
            f"Review:      "
            f"{volume['requires_human_review']}"
        )

        print(
            "Signals:"
        )

        for signal in volume[
            "signals"
        ]:

            print(
                f"  - {signal}"
            )


# =========================================================
# EC2 REPORT
# =========================================================

def print_ec2_report():

    print()

    print(
        "Scanning EC2 instances..."
    )

    instances = (
        scan_idle_ec2_instances()
    )

    if not instances:

        print(
            "No idle EC2 instances found."
        )

        return

    print(
        f"Found {len(instances)} "
        f"idle EC2 instance(s)."
    )

    for instance in instances:

        print()

        print(
            "----------------------------"
        )

        print(
            f"Resource ID: "
            f"{instance['resource_id']}"
        )

        print(
            f"Name:        "
            f"{instance['name']}"
        )

        print(
            f"Service:     "
            f"{instance['service']}"
        )

        print(
            f"State:       "
            f"{instance['state']}"
        )

        print(
            f"Type:        "
            f"{instance['instance_type']}"
        )

        print(
            f"Zone:        "
            f"{instance['availability_zone']}"
        )

        print(
            f"Age:         "
            f"{instance['age_days']} days"
        )

        print(
            f"Avg CPU:     "
            f"{instance['average_cpu_percent']}%"
        )

        print(
            f"Window:      "
            f"{instance['observation_hours']} hours"
        )

        print(
            f"CPU limit:   "
            f"{instance['cpu_threshold_percent']}%"
        )

        print(
            f"Candidate:   "
            f"{instance['cleanup_candidate']}"
        )

        print(
            f"Review:      "
            f"{instance['requires_human_review']}"
        )

        print(
            "Signals:"
        )

        for signal in instance[
            "signals"
        ]:

            print(
                f"  - {signal}"
            )


# =========================================================
# ALB REPORT
# =========================================================

def print_alb_report():

    print()

    print(
        "Scanning Application Load Balancers..."
    )

    load_balancers = (
        scan_idle_load_balancers()
    )

    if not load_balancers:

        print(
            "No idle load balancers found."
        )

        return

    print(
        f"Found {len(load_balancers)} "
        f"load balancer candidate(s)."
    )

    for lb in load_balancers:

        print()

        print(
            "----------------------------"
        )

        print(
            f"Resource ID: "
            f"{lb['resource_id']}"
        )

        print(
            f"Name:        "
            f"{lb['name']}"
        )

        print(
            f"Service:     "
            f"{lb['service']}"
        )

        print(
            f"State:       "
            f"{lb['state']}"
        )

        print(
            f"Age:         "
            f"{lb['age_days']} days"
        )

        print(
            f"Requests:    "
            f"{lb['request_count']}"
        )

        print(
            f"Metric data: "
            f"{lb['request_metric_datapoints']}"
        )

        print(
            f"Target groups: "
            f"{lb['target_group_count']}"
        )

        print(
            f"Targets:     "
            f"{lb['total_targets']}"
        )

        print(
            f"Healthy:     "
            f"{lb['healthy_targets']}"
        )

        print(
            f"Unhealthy:   "
            f"{lb['unhealthy_targets']}"
        )

        print(
            f"Est. cost:   "
            f"${lb['monthly_estimate']}"
            f"/month"
        )

        print(
            f"Currency:    "
            f"{lb['currency']}"
        )

        print(
            f"Estimate:    "
            f"{lb['is_estimate']}"
        )

        print(
            f"Method:      "
            f"{lb['estimate_method']}"
        )

        print(
            f"Candidate:   "
            f"{lb['cleanup_candidate']}"
        )

        print(
            f"Review:      "
            f"{lb['requires_human_review']}"
        )

        print(
            "Signals:"
        )

        for signal in lb[
            "signals"
        ]:

            print(
                f"  - {signal}"
            )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print_ebs_report()

    print_ec2_report()

    print_alb_report()

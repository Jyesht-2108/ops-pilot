import os
from decimal import Decimal, ROUND_HALF_UP


# =========================================================
# CONFIGURED PRICING
# =========================================================

# EBS gp3 storage estimate
GP3_USD_PER_GB_MONTH = Decimal(
    os.getenv(
        "OPSPILOT_GP3_USD_PER_GB_MONTH",
        "0.08",
    )
)


# Application Load Balancer base hourly estimate.
#
# Default is a Mumbai/ap-south-1 reference rate.
# Keep configurable because AWS pricing can change.
ALB_USD_PER_HOUR = Decimal(
    os.getenv(
        "OPSPILOT_ALB_USD_PER_HOUR",
        "0.0239",
    )
)


# Standard approximation for monthly hourly resources
HOURS_PER_MONTH = Decimal("730")


# =========================================================
# MONEY HELPER
# =========================================================

def money(value: Decimal) -> float:
    """
    Round monetary values to 2 decimal places.
    """

    return float(
        value.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


# =========================================================
# EBS COST ESTIMATOR
# =========================================================

def estimate_ebs_monthly_cost(
    size_gb: int,
    volume_type: str,
    iops: int | None = None,
    throughput: int | None = None,
):
    """
    Estimate monthly EBS cost.

    MVP currently supports gp3.

    Baseline gp3 performance:
    - 3000 IOPS
    - 125 MB/s throughput

    Additional provisioned performance charges are not
    included in this hackathon estimate.
    """

    if volume_type != "gp3":

        return {
            "monthly_estimate": None,
            "currency": "USD",
            "is_estimate": True,
            "estimate_method":
                "unsupported_volume_type",
        }

    storage_cost = (
        Decimal(str(size_gb))
        * GP3_USD_PER_GB_MONTH
    )

    return {
        "monthly_estimate":
            money(storage_cost),

        "currency":
            "USD",

        "is_estimate":
            True,

        "estimate_method":
            "configured_gp3_gb_month_rate",

        "rate_usd_per_gb_month":
            float(
                GP3_USD_PER_GB_MONTH
            ),

        "size_gb":
            size_gb,

        "baseline_iops":
            iops,

        "baseline_throughput_mbps":
            throughput,
    }


# =========================================================
# ALB COST ESTIMATOR
# =========================================================

def estimate_alb_monthly_cost():
    """
    Estimate the base monthly cost of an Application
    Load Balancer.

    This MVP estimate:

    base hourly ALB rate × 730 hours

    It intentionally does NOT estimate LCU usage.

    For an idle demo ALB with essentially no traffic,
    this provides a simple and explainable base-cost
    estimate.

    Actual AWS billing may differ.
    """

    monthly_base_cost = (
        ALB_USD_PER_HOUR
        * HOURS_PER_MONTH
    )

    return {
        "monthly_estimate":
            money(monthly_base_cost),

        "currency":
            "USD",

        "is_estimate":
            True,

        "estimate_method":
            "configured_alb_hourly_rate_x_730_excludes_lcu",

        "hourly_rate":
            float(
                ALB_USD_PER_HOUR
            ),

        "hours_per_month":
            int(
                HOURS_PER_MONTH
            ),

        "lcu_cost_included":
            False,
    }


# =========================================================
# LOCAL TEST
# =========================================================

if __name__ == "__main__":

    print(
        "OpsPilot Cost Engine"
    )

    print(
        "===================="
    )

    print()

    print(
        "EBS example:"
    )

    ebs = estimate_ebs_monthly_cost(
        size_gb=1,
        volume_type="gp3",
        iops=3000,
        throughput=125,
    )

    print(
        ebs
    )

    print()

    print(
        "ALB example:"
    )

    alb = (
        estimate_alb_monthly_cost()
    )

    print(
        alb
    )

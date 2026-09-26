import os
import boto3


AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")


def get_session():
    """
    Create an AWS session using the normal AWS credential chain.
    No credentials are hardcoded in OpsPilot.
    """
    return boto3.Session(region_name=AWS_REGION)


def get_ec2_client():
    return get_session().client("ec2")


def get_cloudwatch_client():
    return get_session().client("cloudwatch")


def get_elbv2_client():
    return get_session().client("elbv2")


def get_sts_client():
    return get_session().client("sts")


def verify_connection():
    sts = get_sts_client()

    identity = sts.get_caller_identity()

    return {
        "account": identity["Account"],
        "arn": identity["Arn"],
        "region": AWS_REGION,
        "connected": True,
    }


if __name__ == "__main__":
    result = verify_connection()

    print("OpsPilot AWS connection")
    print("-----------------------")
    print(f"Connected: {result['connected']}")
    print(f"Account:   {result['account']}")
    print(f"Region:    {result['region']}")
    print(f"Identity:  {result['arn']}")
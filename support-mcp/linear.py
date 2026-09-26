import os
import httpx
from dotenv import load_dotenv

load_dotenv()

LINEAR_API_URL = "https://api.linear.app/graphql"
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")


async def get_linear_issue(ticket_id: str) -> dict:
    if not LINEAR_API_KEY:
        raise RuntimeError("LINEAR_API_KEY is not configured")

    query = """
    query GetIssue($id: String!) {
        issue(id: $id) {
            id
            identifier
            title
            description
            url
        }
    }
    """

    headers = {
        "Authorization": LINEAR_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "variables": {
            "id": ticket_id
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            LINEAR_API_URL,
            headers=headers,
            json=payload,
            timeout=20,
        )

    response.raise_for_status()

    result = response.json()

    if "errors" in result:
        raise RuntimeError(str(result["errors"]))

    issue = result.get("data", {}).get("issue")

    if issue is None:
        raise ValueError(f"Ticket '{ticket_id}' was not found")

    return issue
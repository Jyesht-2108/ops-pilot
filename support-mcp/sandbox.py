import json
import time

from daytona import Daytona


REPO_URL = "https://github.com/MaddelaTarun/polaris-payments-api.git"


def run_reproduction() -> dict:
    daytona = Daytona()
    sandbox = None

    try:
        # Create an isolated Daytona sandbox
        sandbox = daytona.create()

        results = {}

        # Clone the test application
        clone = sandbox.process.exec(
            f"git clone {REPO_URL} /home/daytona/workspace/polaris-payments-api",
            timeout=60,
        )

        results["clone"] = {
            "exit_code": clone.exit_code,
            "output": clone.result,
        }

        if clone.exit_code != 0:
            return {
                "status": "failed",
                "stage": "clone",
                "results": results,
            }

        # Install dependencies
        install = sandbox.process.exec(
            "python -m pip install -r requirements.txt",
            cwd="/home/daytona/workspace/polaris-payments-api",
            timeout=120,
        )

        results["install"] = {
            "exit_code": install.exit_code,
            "output": install.result,
        }

        if install.exit_code != 0:
            return {
                "status": "failed",
                "stage": "install",
                "results": results,
            }

        # Start the API in the background
        start = sandbox.process.exec(
            "nohup python -m uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/payments-api.log 2>&1 &",
            cwd="/home/daytona/workspace/polaris-payments-api",
            timeout=10,
        )

        results["start"] = {
            "exit_code": start.exit_code,
            "output": start.result,
        }

        # Give Uvicorn a moment to start
        time.sleep(3)

        # Verify the API is alive
        health = sandbox.process.exec(
            "curl -s -i http://127.0.0.1:8000/health",
            timeout=20,
        )

        results["health"] = {
            "exit_code": health.exit_code,
            "output": health.result,
        }

        # Reproduce TES-5
        reproduction = sandbox.process.exec(
            """curl -s -i -X POST http://127.0.0.1:8000/payments \
-H "Content-Type: application/json" \
-d '{"amount":0}'""",
            timeout=20,
        )

        results["reproduction"] = {
            "exit_code": reproduction.exit_code,
            "output": reproduction.result,
        }

        # Capture application logs
        logs = sandbox.process.exec(
            "cat /tmp/payments-api.log",
            timeout=10,
        )

        results["logs"] = {
            "exit_code": logs.exit_code,
            "output": logs.result,
        }

        return {
            "status": "completed",
            "reproduced": "502 Bad Gateway" in reproduction.result,
            "results": results,
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }

    finally:
        if sandbox is not None:
            try:
                sandbox.delete(wait=True)
            except Exception:
                pass
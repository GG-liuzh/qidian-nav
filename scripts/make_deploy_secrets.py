"""Create deployment secrets locally; existing keys are never overwritten."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.deployment import initialize_deployment_secrets  # noqa: E402


if __name__ == "__main__":
    directory = ROOT / ".runtime" / "deploy-secrets"
    initialize_deployment_secrets(directory)
    print(f"Deployment secrets are ready in {directory}; the directory must remain private.")

"""Run the backend suite; optionally use a configured PostgreSQL test database."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
environment = {**os.environ, "PYTHONUTF8": "1"}
if "--postgres" in sys.argv and not environment.get("TEAM_NAV_TEST_DATABASE_URL", "").strip():
    raise SystemExit(
        "--postgres requires TEAM_NAV_TEST_DATABASE_URL for a dedicated PostgreSQL database "
        "whose name starts with team_nav_test. The tests recreate its tables."
    )
result = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "-x", "--disable-warnings"],
    cwd=ROOT / "backend",
    env=environment,
    check=False,
)
raise SystemExit(result.returncode)

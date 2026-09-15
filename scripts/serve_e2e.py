"""Start a disposable, loopback-only instance for browser tests."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import uvicorn  # noqa: E402
from app.cli import initialize  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

(ROOT / ".runtime").mkdir(exist_ok=True)
runtime = Path(tempfile.mkdtemp(prefix="e2e-", dir=ROOT / ".runtime"))
settings = Settings(
    _env_file=None,
    database_url=f"sqlite:///{(runtime / 'test.db').as_posix()}",
    key_file=runtime / "key",
    setup_token_file=runtime / "token",
    frontend_dist=Path(os.environ.get("TEAM_NAV_E2E_DIST", ROOT / "frontend" / "dist")),
    origins="http://127.0.0.1:4179",
    allowed_hosts="127.0.0.1",
    rate_limit_enabled=False,
    secure_cookies=False,
)
initialize(settings)
settings.setup_token_file.write_text("e2e-only-install-token-not-a-real-secret")
uvicorn.run(create_app(settings), host="127.0.0.1", port=4179, log_level="warning", proxy_headers=False)

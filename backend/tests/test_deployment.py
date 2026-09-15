import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from app.deployment import SECRET_NAMES, initialize_deployment_secrets


def test_deployment_initialization_is_complete_and_idempotent(tmp_path):
    directory = tmp_path / "secrets"
    assert initialize_deployment_secrets(directory) is True
    before = {name: (directory / name).read_bytes() for name in SECRET_NAMES}
    assert len(before["credential.key"]) == 32
    assert len(before["db-password"]) == 64
    assert len(before["setup-token"]) == 48
    assert initialize_deployment_secrets(directory) is False
    assert before == {name: (directory / name).read_bytes() for name in SECRET_NAMES}


def test_separate_deployments_receive_independent_keys(tmp_path):
    for name in ("first", "second"):
        initialize_deployment_secrets(tmp_path / name)
    for name in SECRET_NAMES:
        assert (tmp_path / "first" / name).read_bytes() != (tmp_path / "second" / name).read_bytes()


@pytest.mark.parametrize("missing", SECRET_NAMES)
def test_missing_secret_is_not_silently_replaced(tmp_path, missing):
    directory = tmp_path / "secrets"
    initialize_deployment_secrets(directory)
    (directory / missing).unlink()
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    with pytest.raises(RuntimeError, match="incomplete"):
        initialize_deployment_secrets(directory)
    assert before == {path.name: path.read_bytes() for path in directory.iterdir()}


@pytest.mark.parametrize("name,value", [
    ("credential.key", b"wrong-key-size"),
    ("db-password", b""),
    ("setup-token", b"too-short"),
    ("db-password", b"first-line\nsecond-line"),
])
def test_invalid_existing_secret_fails_without_overwriting(tmp_path, name, value):
    initialize_deployment_secrets(tmp_path)
    (tmp_path / name).write_bytes(value)
    before = {name: (tmp_path / name).read_bytes() for name in SECRET_NAMES}
    with pytest.raises(RuntimeError):
        initialize_deployment_secrets(tmp_path)
    assert before == {name: (tmp_path / name).read_bytes() for name in SECRET_NAMES}


def test_init_command_does_not_print_secret_values(tmp_path):
    script = Path(__file__).resolve().parents[1] / "app" / "deployment.py"
    result = subprocess.run(
        [sys.executable, str(script), "--directory", str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    assert "created" in result.stdout
    for name in ("db-password", "setup-token"):
        assert (tmp_path / name).read_text() not in result.stdout + result.stderr
    repeated = subprocess.run(
        [sys.executable, str(script), "--directory", str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    assert "preserved" in repeated.stdout


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions are only enforced on Linux/macOS")
def test_parent_directory_is_private_and_bind_mounted_secrets_are_readable(tmp_path):
    initialize_deployment_secrets(tmp_path)
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    for name in SECRET_NAMES:
        assert stat.S_IMODE((tmp_path / name).stat().st_mode) == 0o644


@pytest.mark.skipif(os.name != "posix", reason="Symlink creation is not available on all Windows accounts")
def test_existing_symlink_is_rejected(tmp_path):
    directory = tmp_path / "secrets"
    initialize_deployment_secrets(directory)
    (directory / "credential.key").unlink()
    outside = tmp_path / "outside-key"
    outside.write_bytes(b"x" * 32)
    (directory / "credential.key").symlink_to(outside)
    with pytest.raises(RuntimeError, match="regular file"):
        initialize_deployment_secrets(directory)
    assert outside.read_bytes() == b"x" * 32

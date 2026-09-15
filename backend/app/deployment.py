"""Create file-backed Docker Compose secrets without host Python dependencies."""

import argparse
import os
import secrets
from pathlib import Path

SECRET_NAMES = ("db-password", "setup-token", "credential.key")


def validate_secret(path: Path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Secret must be a regular file: {path.name}")
    value = path.read_bytes()
    if path.name == "credential.key":
        if len(value) != 32:
            raise RuntimeError("credential.key must contain exactly 32 bytes. Restore the original key.")
        return
    try:
        text = value.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise RuntimeError(f"Invalid text secret: {path.name}") from None
    if not text or any(character in text for character in ("\r", "\n", "\x00")):
        raise RuntimeError(f"Empty or invalid secret: {path.name}")
    if path.name == "setup-token" and not 20 <= len(text) <= 160:
        raise RuntimeError("setup-token must contain between 20 and 160 characters.")


def initialize_deployment_secrets(directory: Path):
    directory = Path(directory)
    if directory.is_symlink():
        raise RuntimeError("The secrets directory must not be a symbolic link.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths = [directory / name for name in SECRET_NAMES]
    present = [path for path in paths if path.exists() or path.is_symlink()]
    if present and len(present) != len(paths):
        raise RuntimeError(
            "Deployment secrets are incomplete. Refusing to generate replacement keys; "
            "restore the missing files from the matching deployment backup."
        )
    # The private parent protects host access. Compose bind-mounts each 0644 file
    # separately so the non-root web user can read it without owning host files.
    if os.name == "posix":
        directory.chmod(0o700)
    if present:
        for path in paths:
            validate_secret(path)
        for path in paths:
            if os.name == "posix":
                path.chmod(0o644)
        return False
    values = (secrets.token_urlsafe(48).encode(), secrets.token_urlsafe(36).encode(), secrets.token_bytes(32))
    for path, value in zip(paths, values, strict=True):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == "posix":
            path.chmod(0o644)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        created = initialize_deployment_secrets(arguments.directory)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"Deployment initialization failed: {exc}\n")
    print("Deployment secrets created." if created else "Existing deployment secrets validated and preserved.")
    print("Read the setup token using: docker compose exec web cat /run/secrets/setup_token")


if __name__ == "__main__":
    main()

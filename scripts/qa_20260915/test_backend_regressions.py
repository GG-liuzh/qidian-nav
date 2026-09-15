"""Expected-behavior regression tests for the 2026-09-15 exploratory review.

Run this file directly with the project virtualenv; set TEAM_NAV_TEST_DATABASE_URL
and add --postgres to also test PostgreSQL. Existing test discovery is unchanged.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))

import pytest  # noqa: E402
from conftest import h as h  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def checked(response, expected):
    assert response.status_code == expected, (response.status_code, response.text)
    return None if expected == 204 else response.json()


def test_last_active_workspace_admin_cannot_demote_self(h):
    _, inactive_admin = h.member("admin")
    last_admin, last_user = h.member("admin")
    checked(h.admin.patch(f"/api/v1/members/{h.admin_user['id']}", json={
        "version": 1, "role": "member", "active": True,
    }), 200)
    checked(h.admin.patch(f"/api/v1/admin/users/{inactive_admin['id']}", json={
        "version": 1, "is_superadmin": False, "active": False,
    }), 200)
    before = checked(h.admin.get("/api/v1/members"), 200)
    assert sum(row["active"] and row["role"] == "admin" for row in before) == 1

    response = last_admin.patch(f"/api/v1/members/{last_user['id']}", json={
        "version": 1, "role": "member", "active": True,
    })
    after = checked(h.admin.get("/api/v1/members"), 200)
    remaining = sum(row["active"] and row["role"] == "admin" for row in after)
    assert response.status_code == 409, (
        f"Demotion returned {response.status_code}; remaining active workspace administrators: {remaining}"
    )


def test_leaving_permanently_revokes_issued_administrator_invitation(h):
    issuer, user = h.member("admin")
    invitation = checked(issuer.post("/api/v1/invitations", json={"role": "admin"}), 201)
    checked(issuer.post("/api/v1/workspace/leave"), 200)
    checked(h.admin.post("/api/v1/auth/invitation-info", json={"token": invitation["token"]}), 400)
    checked(h.admin.post("/api/v1/workspace/members", json={
        "username": user["username"], "role": "admin",
    }), 201)

    recipient = TestClient(h.app, headers={"Origin": "http://testserver"})
    try:
        response = recipient.post("/api/v1/auth/register", json={
            "username": "old_invite_recipient",
            "display_name": "QA old invitation recipient",
            "password": "qa-only-recipient-password",
            "token": invitation["token"],
        })
        actual_role = response.json().get("role")
        assert response.status_code == 400, (
            f"An invitation issued before leaving returned {response.status_code}; new account role: {actual_role}"
        )
    finally:
        recipient.close()


def test_bookmark_import_skips_url_with_invalid_hostname(h):
    document = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><p>
    <DT><A HREF="https://valid.example/path">Valid bookmark</A>
    <DT><A HREF="https://invalid host.example/path">Invalid bookmark</A>
    </DL><p>"""
    preview = checked(h.admin.post("/api/v1/me/bookmarks/preview", json={"html": document}), 200)
    imported = checked(h.admin.post("/api/v1/me/bookmarks/import", json={"html": document}), 200)
    assert (preview["resources"], preview["skipped_invalid"], imported["imported"]) == (1, 1, 1), (
        f"Preview accepted {preview['resources']} bookmarks and skipped {preview['skipped_invalid']}; "
        f"import saved {imported['imported']} bookmarks, including the invalid hostname"
    )


if __name__ == "__main__":
    os.environ["PYTHONUTF8"] = "1"
    database_label = "sqlite"
    if "--postgres" in sys.argv:
        if not os.environ.get("TEAM_NAV_TEST_DATABASE_URL", "").strip():
            raise SystemExit(
                "--postgres requires TEAM_NAV_TEST_DATABASE_URL for a dedicated PostgreSQL database "
                "whose name starts with team_nav_test. The tests recreate its tables."
            )
    if os.environ.get("TEAM_NAV_TEST_DATABASE_URL", "").strip():
        database_label = "sqlite-postgresql"
    results = ROOT / ".runtime" / "qa-20260915"
    results.mkdir(parents=True, exist_ok=True)
    raise SystemExit(pytest.main([
        str(Path(__file__).resolve()), "-q", "--tb=short", "--disable-warnings",
        f"--junitxml={results / ('backend-' + database_label + '.xml')}",
    ]))

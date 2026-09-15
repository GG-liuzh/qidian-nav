"""Exercise the HTTP boundary, including authenticated visitors to public links."""

import pytest
from conftest import draft_from
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_core import create_account
from test_independent_navigation import register, set_workspace

from app.config import Settings


def public_system(h):
    set_workspace(h, public_enabled=True)
    resource = h.system()
    draft = draft_from(resource, is_public=True)
    draft["endpoints"][0].update(url="https://disabled-secret.example/hidden-needle", enabled=False)
    response = h.admin.patch(f"/api/v1/resources/{resource['id']}", json=draft)
    assert response.status_code == 200, response.text
    return response.json()


def test_public_projection_is_identical_for_guests_and_signed_in_outsiders(h):
    resource = public_system(h)
    outsider, _ = register(h)
    guest = TestClient(h.app)
    public = guest.get("/api/v1/public/navigation").json()["items"][0]
    detail = outsider.get(f"/api/v1/resources/{resource['id']}")
    assert detail.status_code == 200
    for payload in (public, detail.json()):
        assert "disabled-secret" not in str(payload)
        assert "maintainer_id" not in payload and "version" not in payload
        assert len(payload["endpoints"]) == 2
    for path in ("/api/v1/public/navigation?q=hidden-needle", "/api/v1/public/navigation?q=disabled-secret"):
        assert guest.get(path).json()["total"] == 0
    assert outsider.put(f"/api/v1/me/favorites/{resource['id']}").status_code == 204
    for view in ("favorites", "recent"):
        assert outsider.get(f"/api/v1/resources?view={view}&q=hidden-needle").json()["total"] == 0
    disabled_id = resource["endpoints"][0]["id"]
    assert outsider.put(f"/api/v1/me/shortcuts/{disabled_id}").status_code == 404
    assert outsider.post("/api/v1/me/visits", json={"endpoint_id": disabled_id}).status_code == 404
    assert outsider.get(f"/api/v1/endpoints/{disabled_id}/credentials").status_code == 404


def test_disabling_endpoint_revokes_saved_public_references(h):
    set_workspace(h, public_enabled=True)
    resource = h.resource(is_public=True)
    outsider, _ = register(h)
    endpoint_id = resource["endpoints"][0]["id"]
    assert outsider.put(f"/api/v1/me/favorites/{resource['id']}").status_code == 204
    assert outsider.put(f"/api/v1/me/shortcuts/{endpoint_id}").status_code == 204
    assert outsider.post("/api/v1/me/visits", json={"endpoint_id": endpoint_id}).status_code == 204
    draft = draft_from(resource)
    draft["endpoints"][0]["enabled"] = False
    assert h.admin.patch(f"/api/v1/resources/{resource['id']}", json=draft).status_code == 200
    assert TestClient(h.app).get("/api/v1/public/navigation").json()["total"] == 0
    assert outsider.get(f"/api/v1/resources/{resource['id']}").status_code == 404
    for path in ("/api/v1/me/favorites", "/api/v1/me/shortcuts", "/api/v1/resources?view=recent"):
        assert resource["id"] not in outsider.get(path).text
    assert h.admin.get(f"/api/v1/resources/{resource['id']}").status_code == 200


def test_disabled_environment_is_not_published_and_private_home_id_is_not_exposed(h):
    resource = public_system(h)
    env_id = resource["endpoints"][1]["environment_id"]
    env = next(item for item in h.admin.get("/api/v1/catalog").json()["environments"] if item["id"] == env_id)
    env_payload = {
        key: env[key] for key in ("scope", "key", "label", "kind", "enabled", "sort_order", "version")
    }
    env_payload["enabled"] = False
    assert h.admin.patch(f"/api/v1/environments/{env_id}", json=env_payload).status_code == 200
    public = TestClient(h.app).get("/api/v1/public/navigation").json()
    assert len(public["items"][0]["endpoints"]) == 1
    assert env_id not in str(public["environments"])
    set_workspace(h, public_enabled=False)
    public = TestClient(h.app).get("/api/v1/public/navigation").json()
    assert public["workspace_id"] is None and public["items"] == []


@pytest.mark.parametrize("state", ["active", "pending", "disabled"])
def test_credential_lists_never_decrypt_usernames(h, state):
    resource = h.resource()
    account = create_account(h, resource)
    member, _ = h.member()
    if state != "active":
        assert (
            h.admin.patch(
                f"/api/v1/credentials/{account['id']}",
                json={"name": account["name"], "version": account["version"], "status": state},
            ).status_code
            == 200
        )
    for client in (h.admin, member):
        response = client.get(f"/api/v1/endpoints/{account['endpoint_id']}/credentials")
        assert response.status_code == 200
        assert "realistic-test-user" not in response.text and "SENSITIVE-test-pass" not in response.text
        assert response.json()[0]["username"] is None
        read = client.post(
            f"/api/v1/credentials/{account['id']}/access", json={"field": "username", "purpose": "reveal"}
        )
        assert read.status_code == (200 if state == "active" else 403)


def test_removed_member_loses_all_team_read_paths(h):
    member, user = h.member()
    category = h.category()
    resource = h.resource(category=category, name="TEAM-PRIVATE-NEEDLE")
    account = create_account(h, resource)
    endpoint_id = account["endpoint_id"]
    member.put(f"/api/v1/me/favorites/{resource['id']}")
    member.put(f"/api/v1/me/shortcuts/{endpoint_id}")
    member.post("/api/v1/me/visits", json={"endpoint_id": endpoint_id})
    record = next(row for row in h.admin.get("/api/v1/members").json() if row["id"] == user["id"])
    assert (
        h.admin.patch(
            f"/api/v1/members/{user['id']}",
            json={"role": "member", "active": False, "version": record["version"]},
        ).status_code
        == 200
    )
    member.headers["X-Workspace-ID"] = h.admin_user["workspace"]["id"]
    for path in (
        "/resources?view=team",
        "/resources?view=favorites",
        "/resources?view=recent",
        "/catalog",
        "/me/shortcuts",
        "/me/favorites",
        "/exports?scope=team",
        "/audit-events",
        "/trash",
        "/feedback",
    ):
        response = member.get(f"/api/v1{path}")
        assert response.status_code == 200, response.text
        assert resource["id"] not in response.text and "TEAM-PRIVATE-NEEDLE" not in response.text
    for path in (
        f"/resources/{resource['id']}",
        f"/resources/{resource['id']}/revisions",
        f"/endpoints/{endpoint_id}/credentials",
    ):
        assert member.get(f"/api/v1{path}").status_code == 404
    assert (
        member.post(
            f"/api/v1/credentials/{account['id']}/access", json={"field": "password", "purpose": "copy"}
        ).status_code
        == 404
    )


def test_password_change_invalidates_outstanding_admin_reset(h):
    member, user = h.member()
    token = h.admin.post(f"/api/v1/admin/users/{user['id']}/recovery").json()["token"]
    response = member.post(
        "/api/v1/me/password",
        json={"old_password": "test-member-password-2026", "password": "rotated-private-password"},
    )
    assert response.status_code == 204
    guest = TestClient(h.app, headers={"Origin": "http://testserver"})
    assert (
        guest.post(
            "/api/v1/auth/reset-token", json={"token": token, "password": "should-never-take-effect"}
        ).status_code
        == 400
    )


def test_recovery_reset_invalidates_outstanding_admin_reset(h):
    _, user = h.member()
    token = h.admin.post(f"/api/v1/admin/users/{user['id']}/recovery").json()["token"]
    guest = TestClient(h.app, headers={"Origin": "http://testserver"})
    assert (
        guest.post(
            "/api/v1/auth/reset",
            json={
                "username": user["username"],
                "recovery_code": user["recovery_code"],
                "password": "new-recovery-password",
            },
        ).status_code
        == 200
    )
    assert (
        guest.post(
            "/api/v1/auth/reset-token", json={"token": token, "password": "should-never-take-effect"}
        ).status_code
        == 400
    )


def test_removing_admin_in_one_space_preserves_other_space_invitations(h):
    admin, user = h.member("admin")
    first_id = h.admin_user["workspace"]["id"]
    created = h.admin.post("/api/v1/workspace", json={"name": "第二空间"}).json()
    second_id = created["workspace"]["id"]
    assert (
        h.admin.post(
            "/api/v1/workspace/members", json={"username": user["username"], "role": "admin"}
        ).status_code
        == 201
    )
    admin.headers["X-Workspace-ID"] = second_id
    token = admin.post("/api/v1/invitations", json={}).json()["token"]
    h.admin.headers["X-Workspace-ID"] = first_id
    record = next(row for row in h.admin.get("/api/v1/members").json() if row["id"] == user["id"])
    assert (
        h.admin.patch(
            f"/api/v1/members/{user['id']}",
            json={"role": "member", "active": True, "version": record["version"]},
        ).status_code
        == 200
    )
    guest = TestClient(h.app, headers={"Origin": "http://testserver"})
    assert guest.post("/api/v1/auth/invitation-info", json={"token": token}).status_code == 200


def test_security_headers_also_cover_rejected_requests(h):
    response = h.admin.post("/api/v1/me/password", headers={"Origin": "https://untrusted.example"}, json={})
    assert response.status_code == 403
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert "frame-ancestors 'none'" in response.headers.get("content-security-policy", "")


def test_closed_registration_still_allows_valid_invitations(h):
    h.settings.registration_enabled = False
    guest = TestClient(h.app, headers={"Origin": "http://testserver"})
    payload = {"username": "invited-person", "display_name": "受邀成员", "password": "long-invited-password"}
    assert guest.post("/api/v1/auth/register", json=payload).status_code == 403
    assert guest.get("/api/v1/setup/status").json()["registration_enabled"] is False
    payload["token"] = h.admin.post("/api/v1/invitations", json={}).json()["token"]
    assert guest.post("/api/v1/auth/register", json=payload).status_code == 201


def test_password_confirmation_is_rate_limited_across_endpoints(h):
    h.settings.rate_limit_enabled = True
    for _ in range(10):
        assert (
            h.admin.post("/api/v1/me/recovery-code", json={"password": "incorrect-password"}).status_code
            == 400
        )
    response = h.admin.post(
        "/api/v1/me/password", json={"old_password": "incorrect-password", "password": "a-long-new-password"}
    )
    assert response.status_code == 429
    assert response.headers["retry-after"]


def test_unauthenticated_requests_cannot_read_private_api_families(h):
    resource = h.resource(name="NEVER-PUBLIC")
    account = create_account(h, resource)
    guest = TestClient(h.app)
    paths = [
        "/resources",
        f"/resources/{resource['id']}",
        f"/resources/{resource['id']}/revisions",
        f"/endpoints/{account['endpoint_id']}/credentials",
        "/catalog",
        "/members",
        "/invitations",
        "/me",
        "/me/favorites",
        "/me/shortcuts",
        "/exports",
        "/audit-events",
        "/trash",
        "/feedback",
        "/workspaces",
        "/admin/users",
        "/admin/workspaces",
        "/admin/events",
    ]
    for path in paths:
        response = guest.get(f"/api/v1{path}")
        assert response.status_code == 401, (path, response.text)
        assert "NEVER-PUBLIC" not in response.text
        assert "realistic-test-user" not in response.text
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "override",
    [
        {"secure_cookies": False},
        {"rate_limit_enabled": False},
        {"allowed_hosts": "*"},
        {"origins": "http://nav.example"},
        {"origins": "https://other.example"},
        {"origins": "https://nav.example/untrusted-path"},
    ],
)
def test_production_configuration_rejects_unsafe_defaults(override):
    values = dict(
        _env_file=None,
        environment="production",
        origins="https://nav.example",
        allowed_hosts="nav.example",
        secure_cookies=True,
        rate_limit_enabled=True,
    )
    with pytest.raises(ValidationError):
        Settings(**(values | override))


def test_production_configuration_allows_exact_https_origins():
    settings = Settings(
        _env_file=None,
        environment="production",
        origins="https://nav.example",
        allowed_hosts="nav.example,127.0.0.1",
        secure_cookies=True,
    )
    assert settings.origin_list == ["https://nav.example"]


def test_exact_url_lookup_accepts_long_links_without_disclosing_other_users_links(h):
    url = "https://docs.example/reference?section=" + "a" * 300
    owner, _ = h.member()
    resource = h.resource("personal", owner, endpoints=[{"url": url}])
    result = owner.get("/api/v1/resources", params={"view": "personal", "url": url})
    assert result.status_code == 200 and result.json()["items"][0]["id"] == resource["id"]
    assert h.admin.get("/api/v1/resources", params={"view": "personal", "url": url}).json()["total"] == 0

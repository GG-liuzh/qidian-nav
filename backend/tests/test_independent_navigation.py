import copy
import json

from conftest import draft_from
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_core import create_account

from app.cli import initialize
from app.main import create_app
from app.models import (
    TransferReceipt,
    User,
)


def register(h, username="personal-user"):
    client = TestClient(h.app, headers={"Origin": "http://testserver"})
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "display_name": username,
            "password": "personal-test-password",
            "remember_me": True,
        },
    )
    assert response.status_code == 201, response.text
    user = response.json()
    client.headers["X-CSRF-Token"] = user["csrf_token"]
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    return client, user


def set_workspace(h, **values):
    response = h.admin.patch("/api/v1/workspace", json={"name": "测试研发部", **values})
    assert response.status_code == 200, response.text


def personal_account(client, resource):
    response = client.post(
        f"/api/v1/endpoints/{resource['endpoints'][0]['id']}/credentials",
        json={
            "name": "私人测试账号",
            "username": "private-account-user",
            "password": " private-secret-keeps-spaces ",
            "usage_note": "只属于个人",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_personal_registration_needs_no_department_and_is_isolated(h):
    client, user = register(h)
    assert user["role"] == "personal" and user["workspace"] is None
    assert user["has_recovery_code"] and user["recovery_code"]
    catalog = client.get("/api/v1/catalog").json()
    assert len(catalog["environments"]) == 3
    assert all(row["scope"] == "personal" for row in catalog["environments"])
    resource = h.resource("personal", client, name="独立个人内容")
    other, _ = register(h, "another-person")
    for outsider in (other, h.admin):
        assert outsider.get(f"/api/v1/resources/{resource['id']}").status_code == 404
        assert outsider.get("/api/v1/resources?view=personal").json()["total"] == 0
    assert client.get("/api/v1/members").json() == []
    assert client.get("/api/v1/resources?view=team").json()["total"] == 0
    assert client.post("/api/v1/resources", json=h.draft()).status_code == 403
    assert client.post("/api/v1/workspace", json={"name": "非法部门"}).status_code == 403
    assert (
        client.post(
            "/api/v1/feedback", json={"kind": "add", "title": "无团队", "url": "https://example.com/"}
        ).status_code
        == 403
    )


def test_public_navigation_exposes_only_explicitly_published_metadata(h):
    guest = TestClient(h.app)
    assert guest.get("/api/v1/public/navigation").json()["total"] == 0
    private_category = h.category(name="PRIVATE-CATEGORY")
    h.resource(category=private_category, name="PRIVATE-TEAM-RESOURCE")
    assert h.admin.post("/api/v1/resources", json=h.draft(is_public=True)).status_code == 422
    set_workspace(h, public_enabled=True)
    category = h.category(name="公开目录")
    resource = h.resource(category=category, name="公开订单文档", is_public=True)
    account = create_account(h, resource)
    h.resource("personal", name="PRIVATE-PERSONAL-RESOURCE")
    response = guest.get("/api/v1/public/navigation")
    assert response.status_code == 200 and response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == resource["id"]
    for secret in ("PRIVATE-", "SENSITIVE-test-pass", "realistic-test-user", account["id"], "credentials"):
        assert secret not in response.text
    assert guest.get(f"/api/v1/endpoints/{resource['endpoints'][0]['id']}/credentials").status_code == 401
    outsider, _ = register(h)
    assert outsider.get(f"/api/v1/resources/{resource['id']}").json()["can_edit"] is False
    assert outsider.get(f"/api/v1/endpoints/{resource['endpoints'][0]['id']}/credentials").json() == []
    assert (
        outsider.post(
            f"/api/v1/credentials/{account['id']}/access", json={"field": "password", "purpose": "copy"}
        ).status_code
        == 403
    )
    assert guest.get("/api/v1/public/navigation", params={"q": "PRIVATE"}).json()["total"] == 0
    assert (
        h.admin.patch(
            f"/api/v1/resources/{resource['id']}", json=draft_from(resource, is_public=False)
        ).status_code
        == 200
    )
    assert guest.get("/api/v1/public/navigation").json()["total"] == 0
    set_workspace(h, public_enabled=False)
    assert guest.get("/api/v1/public/navigation").json()["title"] == "栖点导航"


def test_personal_public_page_does_not_expose_other_personal_data(h):
    client, user = register(h)
    public = h.resource("personal", client, name="公开学习入口", is_public=True)
    personal_account(client, public)
    h.resource("personal", client, name="PRIVATE-NOTES")
    guest = TestClient(h.app)
    response = guest.get("/api/v1/public/navigation", params={"owner": user["id"]})
    assert response.status_code == 200 and response.json()["total"] == 1
    assert "PRIVATE-NOTES" not in response.text and "private-account-user" not in response.text
    assert h.admin.get("/api/v1/resources?view=personal").json()["total"] == 0
    assert h.admin.get(f"/api/v1/resources/{public['id']}").json()["can_grant"] is False
    assert (
        h.admin.put(
            f"/api/v1/resources/{public['id']}/grants/{h.admin_user['id']}", json={"can_read": True}
        ).status_code
        == 410
    )
    assert h.admin.post("/api/v1/me/transfer/export", json={}).json()["resources"] == []
    updated = client.patch(f"/api/v1/resources/{public['id']}", json=draft_from(public, is_public=False))
    assert updated.status_code == 200, updated.text
    assert guest.get("/api/v1/public/navigation", params={"owner": user["id"]}).status_code == 404


def test_maintenance_roles_and_publication_stays_admin(h):
    member, _ = h.member()
    maintainer, user = h.member("maintainer")
    category = h.category()
    set_workspace(h, public_enabled=True)
    assert member.post("/api/v1/resources", json=h.draft(category=category)).status_code == 403
    resource = h.resource(client=maintainer, category=category)
    assert (
        maintainer.patch(
            f"/api/v1/resources/{resource['id']}", json=draft_from(resource, is_public=True)
        ).status_code
        == 403
    )
    assert (
        maintainer.post("/api/v1/categories", json={"scope": "team", "name": "越权目录"}).status_code == 403
    )
    account = create_account(h, resource)
    assert (
        member.post(
            f"/api/v1/credentials/{account['id']}/access", json={"field": "password", "purpose": "copy"}
        ).status_code
        == 200
    )
    assert member.patch(f"/api/v1/resources/{resource['id']}", json=draft_from(resource)).status_code == 403
    assert user["id"] == resource["maintainer_id"]


def test_leaving_and_member_removal_preserve_personal_session_and_credentials(h):
    client, user = register(h)
    personal_env = client.get("/api/v1/catalog").json()["environments"][0]
    personal = h.resource(
        "personal",
        client,
        type="system",
        name="个人系统",
        endpoints=[{"url": "https://my-system.example/", "environment_id": personal_env["id"]}],
    )
    personal_secret = personal_account(client, personal)
    token = h.admin.post("/api/v1/invitations", json={}).json()["token"]
    joined = client.post("/api/v1/auth/join", json={"token": token})
    assert joined.status_code == 200 and joined.json()["role"] == "member"
    team_env = next(
        row for row in h.admin.get("/api/v1/catalog").json()["environments"] if row["scope"] == "team"
    )
    assert (
        client.post(
            "/api/v1/resources",
            json=h.draft(
                "personal",
                type="system",
                endpoints=[{"environment_id": team_env["id"], "url": "https://bad.example/"}],
            ),
        ).status_code
        == 422
    )
    set_workspace(h, public_enabled=True)
    team = h.resource(is_public=True)
    team_secret = create_account(h, team)
    h.admin.put(f"/api/v1/credentials/{team_secret['id']}/grants/{user['id']}", json={"can_read": True})
    access = {"field": "password", "purpose": "copy"}
    assert client.post(f"/api/v1/credentials/{team_secret['id']}/access", json=access).status_code == 200
    assert (
        h.admin.patch(
            f"/api/v1/members/{user['id']}", json={"version": 1, "role": "member", "active": False}
        ).status_code
        == 200
    )
    assert client.get("/api/v1/me").json()["workspace"] is None
    assert client.get(f"/api/v1/resources/{personal['id']}").status_code == 200
    assert (
        client.post(f"/api/v1/credentials/{personal_secret['id']}/access", json=access).json()["value"]
        == " private-secret-keeps-spaces "
    )
    assert client.post(f"/api/v1/credentials/{team_secret['id']}/access", json=access).status_code == 403
    assert client.get("/api/v1/resources?view=team").json()["total"] == 0
    assert all(row["scope"] == "personal" for row in client.get("/api/v1/catalog").json()["environments"])
    token = h.admin.post("/api/v1/invitations", json={}).json()["token"]
    assert client.post("/api/v1/auth/join", json={"token": token}).status_code == 200
    assert client.post("/api/v1/workspace/leave").json()["role"] == "personal"
    assert client.get(f"/api/v1/resources/{personal['id']}").status_code == 200
    assert h.admin.post("/api/v1/workspace/leave").status_code == 409
    with h.app.state.sessions() as db:
        assert db.get(User, user["id"]).active


def test_recovery_is_personal_rotates_code_and_cannot_be_reset_by_team_admin(h):
    member, user = h.member()
    assert h.admin.post(f"/api/v1/members/{user['id']}/reset").status_code == 403
    assert member.post("/api/v1/me/recovery-code", json={"password": "wrong"}).status_code == 400
    renewed = member.post("/api/v1/me/recovery-code", json={"password": "test-member-password-2026"})
    assert renewed.status_code == 200
    code = renewed.json()["recovery_code"]
    stranger = TestClient(h.app, headers={"Origin": "http://testserver"})
    payload = {
        "username": user["username"],
        "password": "new-personal-password",
        "recovery_code": user["recovery_code"],
    }
    assert stranger.post("/api/v1/auth/reset", json=payload).status_code == 400
    response = stranger.post("/api/v1/auth/reset", json={**payload, "recovery_code": code})
    assert response.status_code == 200 and response.json()["recovery_code"] != code
    assert member.get("/api/v1/me").status_code == 401
    assert stranger.post("/api/v1/auth/reset", json={**payload, "recovery_code": code}).status_code == 400
    assert (
        stranger.post(
            "/api/v1/auth/login", json={"username": user["username"], "password": "new-personal-password"}
        ).status_code
        == 200
    )


def test_personal_transfer_roundtrip_to_new_instance_is_encrypted_private_and_idempotent(h, tmp_path):
    client, user = h.member()
    root = h.category("personal", client, name="迁移分组")
    child = h.category("personal", client, name="迁移子分组", parent_id=root["id"])
    personal_env = next(
        row for row in client.get("/api/v1/catalog").json()["environments"] if row["scope"] == "personal"
    )
    resource = h.resource(
        "personal",
        client,
        child,
        type="system",
        name="迁移个人系统",
        is_public=True,
        endpoints=[{"url": "https://move.example/", "environment_id": personal_env["id"]}],
    )
    account = personal_account(client, resource)
    team = h.resource(name="TEAM-MUST-STAY")
    client.put(f"/api/v1/me/favorites/{resource['id']}")
    client.put(f"/api/v1/me/favorites/{team['id']}")
    assert client.put(f"/api/v1/me/shortcuts/{resource['endpoints'][0]['id']}").status_code in (200, 201, 204)
    client.patch("/api/v1/me/preferences", json={"theme": "dark", "layout": "list", "record_visits": False})
    plain = client.post("/api/v1/me/transfer/export", json={})
    assert plain.status_code == 200
    assert "TEAM-MUST-STAY" not in plain.text and "private-secret" not in plain.text
    assert len(plain.json()["resources"]) == 1
    assert client.post("/api/v1/me/transfer/export", json={"include_credentials": True}).status_code == 422
    passphrase = "migration-passphrase-2026"
    response = client.post(
        "/api/v1/me/transfer/export", json={"include_credentials": True, "passphrase": passphrase}
    )
    assert response.status_code == 200, response.text
    assert "private-secret" not in response.text and "move.example" not in response.text
    package = response.json()
    target_settings = h.settings.model_copy(
        update={
            "database_url": f"sqlite:///{(tmp_path / 'new-personal.db').as_posix()}",
            "key_file": tmp_path / "new-key",
            "setup_token_file": tmp_path / "new-token",
        }
    )
    initialize(target_settings)
    assert target_settings.key_file.read_bytes() != h.settings.key_file.read_bytes()
    target_app = create_app(target_settings)
    with TestClient(target_app, headers={"Origin": "http://testserver"}) as target:
        assert target.get("/api/v1/public/navigation").json()["total"] == 0
        installed = target.post(
            "/api/v1/setup",
            json={
                "username": "independent",
                "display_name": "自己的电脑",
                "password": "my-independent-password",
                "token": target_settings.setup_token_file.read_text(),
            },
        )
        assert installed.status_code == 201 and installed.json()["workspace"] is None
        assert installed.json()["has_team"] is False
        target.headers["X-CSRF-Token"] = installed.json()["csrf_token"]
        payload = {"package": package, "passphrase": passphrase}
        assert (
            target.post(
                "/api/v1/me/transfer/preview", json={**payload, "passphrase": "wrong-passphrase"}
            ).status_code
            == 422
        )
        preview = target.post("/api/v1/me/transfer/preview", json=payload).json()
        assert preview["resources"] == 1 and preview["credentials"] == 1 and preview["categories"] == 2
        imported = target.post("/api/v1/me/transfer/import", json=payload)
        assert imported.status_code == 200, imported.text
        assert imported.json()["imported"] == 1 and imported.json()["credentials"] == 1
        duplicate = target.post("/api/v1/me/transfer/import", json=payload)
        assert duplicate.json()["already_imported"]
        result = target.get("/api/v1/resources?view=personal").json()
        assert result["total"] == 1
        new = result["items"][0]
        assert new["id"] != resource["id"] and new["is_public"] is False
        assert new["maintainer_id"] == installed.json()["id"]
        assert new["endpoints"][0]["environment_id"] != personal_env["id"]
        credentials = target.get(f"/api/v1/endpoints/{new['endpoints'][0]['id']}/credentials").json()
        assert credentials[0]["id"] != account["id"]
        assert (
            target.post(
                f"/api/v1/credentials/{credentials[0]['id']}/access",
                json={"field": "password", "purpose": "copy"},
            ).json()["value"]
            == " private-secret-keeps-spaces "
        )
        assert target.get("/api/v1/resources?view=favorites").json()["total"] == 1
        assert len(target.get("/api/v1/me/shortcuts").json()) == 1
        assert target.get("/api/v1/me").json()["preferences"]["theme"] == "dark"
        assert target.get("/api/v1/public/navigation").json()["total"] == 0
        assert target.post("/api/v1/workspace", json={"name": "之后启用的部门"}).status_code == 201
        assert target.get("/api/v1/me").json()["workspace"]["role"] == "admin"


def test_transfer_validation_rejects_invalid_packages_without_partial_import(h):
    source, _ = register(h, "source")
    target, target_user = register(h, "target")
    root = h.category("personal", source, name="完整导入分组")
    resource = h.resource("personal", source, root)
    h.resource("personal", source, root, name="第二个链接", endpoints=[{"url": "https://second.example/"}])
    bundle = source.post("/api/v1/me/transfer/export", json={}).json()
    variants = []
    invalid = copy.deepcopy(bundle)
    invalid["resources"][1]["tags"] = ["x" * 31]
    variants.append(invalid)
    invalid = copy.deepcopy(bundle)
    invalid["resources"][1]["endpoints"][0]["url"] = "javascript:alert(1)"
    variants.append(invalid)
    invalid = copy.deepcopy(bundle)
    invalid["resources"][1]["category_id"] = "missing"
    variants.append(invalid)
    invalid = copy.deepcopy(bundle)
    invalid["categories"][0]["parent_id"] = root["id"]
    variants.append(invalid)
    invalid = copy.deepcopy(bundle)
    invalid["resources"][0]["endpoints"][0]["credentials"] = [
        {"name": "明文禁止", "username": "u", "password": "p"}
    ]
    variants.append(invalid)
    invalid = copy.deepcopy(bundle)
    invalid["favorites"] = [resource["id"], resource["id"]]
    variants.append(invalid)
    for invalid in variants:
        response = target.post("/api/v1/me/transfer/import", json={"package": invalid})
        assert response.status_code == 422, response.text
        assert target.get("/api/v1/resources?view=personal").json()["total"] == 0
        assert target.get("/api/v1/catalog").json()["categories"] == []
        with h.app.state.sessions() as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(TransferReceipt)
                    .where(TransferReceipt.user_id == target_user["id"])
                )
                == 0
            )
    assert target.post("/api/v1/me/transfer/import", json={"package": bundle}).json()["imported"] == 2
    fresh = source.post("/api/v1/me/transfer/export", json={}).json()
    assert len(target.post("/api/v1/me/transfer/preview", json={"package": fresh}).json()["duplicates"]) == 2
    skipped = target.post("/api/v1/me/transfer/import", json={"package": fresh}).json()
    assert skipped["imported"] == 0 and skipped["skipped"] == 2
    altered = copy.deepcopy(bundle)
    altered["resources"][0]["name"] = "changed"
    assert target.post("/api/v1/me/transfer/import", json={"package": altered}).status_code == 409
    assert "private-secret" not in json.dumps(target.get("/api/v1/audit-events").json())

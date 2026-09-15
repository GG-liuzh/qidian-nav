import os
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.cli import initialize
from app.config import Settings
from app.db import Base, make_engine
from app.main import create_app


@dataclass
class Harness:
    app: object
    admin: TestClient
    settings: Settings
    admin_user: dict
    counter: int = 0

    def member(self, role="member"):
        self.counter += 1
        token = self.admin.post("/api/v1/invitations", json={"role": role}).json()["token"]
        client = TestClient(self.app, headers={"Origin": "http://testserver"})
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": f"user{self.counter}",
                "display_name": f"成员{self.counter}",
                "password": "test-member-password-2026",
                "token": token,
            },
        )
        assert response.status_code == 201, response.text
        user = response.json()
        client.headers["X-CSRF-Token"] = user["csrf_token"]
        return client, user

    def category(self, scope="team", client=None, **values):
        response = (client or self.admin).post(
            "/api/v1/categories", json={"scope": scope, "name": "交易平台", **values}
        )
        assert response.status_code == 201, response.text
        return response.json()

    def resource(self, scope="team", client=None, category=None, **values):
        response = (client or self.admin).post(
            "/api/v1/resources", json=self.draft(scope, category, **values)
        )
        assert response.status_code == 201, response.text
        return response.json()

    def draft(self, scope="team", category=None, **values):
        return {
            "scope": scope,
            "type": "bookmark",
            "name": "订单文档",
            "category_id": category["id"] if category else None,
            "endpoints": [{"url": "https://docs.example/orders"}],
            **values,
        }

    def system(self):
        envs = [
            row for row in self.admin.get("/api/v1/catalog").json()["environments"] if row["scope"] == "team"
        ]
        return self.resource(
            type="system",
            name="订单中心",
            endpoints=[
                {"environment_id": env["id"], "url": f"https://oms-{env['key']}.example/"} for env in envs
            ],
        )


def draft_from(resource, **changes):
    fields = {
        key: resource[key]
        for key in (
            "scope",
            "type",
            "name",
            "category_id",
            "aliases",
            "description",
            "tags",
            "icon",
            "maintainer_id",
            "status",
            "version",
            "is_public",
        )
    }
    fields["endpoints"] = [
        {"environment_id": row["environment_id"], "url": row["url"], "enabled": row["configured_enabled"]}
        for row in resource["endpoints"]
    ]
    return {**fields, **changes}


@pytest.fixture(params=["sqlite", "postgresql"])
def h(request, tmp_path):
    if request.param == "postgresql":
        url = os.environ.get("TEAM_NAV_TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set TEAM_NAV_TEST_DATABASE_URL for the isolated PostgreSQL test database")
        if not (make_url(url).database or "").startswith("team_nav_test"):
            pytest.fail("The integration database name must start with team_nav_test")
        engine = make_engine(url)
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
    else:
        url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    settings = Settings(
        _env_file=None,
        database_url=url,
        key_file=tmp_path / "key",
        setup_token_file=tmp_path / "setup-token",
        frontend_dist=tmp_path / "frontend",
        origins="http://testserver",
        allowed_hosts="testserver",
        rate_limit_enabled=False,
    )
    initialize(settings)
    app = create_app(settings)
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        response = client.post(
            "/api/v1/setup",
            json={
                "username": "admin",
                "display_name": "管理员",
                "password": "admin-private-pass-2026",
                "workspace_name": "测试研发部",
                "token": settings.setup_token_file.read_text(),
            },
        )
        assert response.status_code == 201, response.text
        user = response.json()
        client.headers["X-CSRF-Token"] = user["csrf_token"]
        yield Harness(app, client, settings, user)

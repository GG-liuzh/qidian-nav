import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("scope", ["team", "personal"])
def test_resource_endpoints_follow_current_environment_order(h, scope):
    if scope == "team":
        response = h.admin.patch(
            "/api/v1/workspace", json={"name": "测试研发部", "public_enabled": True}
        )
        assert response.status_code == 200, response.text
    environments = [
        row for row in h.admin.get("/api/v1/catalog").json()["environments"] if row["scope"] == scope
    ]
    # Reverse identifier order so the old endpoint.environment_key ordering always fails.
    ordered = sorted(environments, key=lambda row: row["id"], reverse=True)
    for index, environment in enumerate(ordered):
        response = h.admin.patch(
            f"/api/v1/environments/{environment['id']}",
            json={key: value for key, value in environment.items() if key != "id"}
            | {"sort_order": index * 10},
        )
        assert response.status_code == 200, response.text
        ordered[index] = response.json()
    resource = h.resource(
        scope,
        type="system",
        is_public=True,
        endpoints=[
            {"environment_id": row["id"], "url": f"https://{row['key']}.example/"}
            for row in environments
        ],
    )
    expected = [row["id"] for row in ordered]
    assert [row["environment_id"] for row in resource["endpoints"]] == expected
    public_params = {"owner": h.admin_user["id"]} if scope == "personal" else {}

    def assert_order():
        detail = h.admin.get(f"/api/v1/resources/{resource['id']}").json()
        listing = h.admin.get("/api/v1/resources", params={"view": scope}).json()["items"][0]
        public = TestClient(h.app).get("/api/v1/public/navigation", params=public_params)
        assert public.status_code == 200, public.text
        for item in (detail, listing, public.json()["items"][0]):
            assert [row["environment_id"] for row in item["endpoints"]] == expected

    assert_order()
    first = ordered[0]
    response = h.admin.patch(
        f"/api/v1/environments/{first['id']}",
        json={key: value for key, value in first.items() if key != "id"} | {"sort_order": 100},
    )
    assert response.status_code == 200, response.text
    expected = expected[1:] + expected[:1]
    assert_order()

    # The outer join must also retain bookmarks without an environment.
    bookmark = h.resource(scope, is_public=True)
    assert len(bookmark["endpoints"]) == 1
    assert bookmark["endpoints"][0]["environment_id"] is None

def test_old_console_spaces_return_404(client):
    assert client.get("/api/v1/console").status_code == 404
    assert client.get("/api/v1/console/").status_code == 404
    assert client.get("/api/v1/tenant-console").status_code == 404
    assert client.get("/api/v1/tenant-app").status_code == 404


def test_app_roles_routes_are_canonical(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]

    assert "/api/v1/app/roles" in paths
    assert "/api/v1/app/roles/{role_id}" in paths
    assert "/api/v1/app/roles/{role_id}/permissions" in paths
    assert "/api/v1/app/permissions" in paths

    assert "/api/v1/app/roles/roles" not in paths
    assert "/api/v1/app/roles/roles/{role_id}" not in paths
    assert "/api/v1/app/providers" not in paths

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_spa_html_is_not_cached_but_hashed_assets_are(tmp_path, monkeypatch):
    from app import main as main_module

    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>app</body></html>", encoding="utf-8")
    (assets / "app-abc123.js").write_text("console.log('app')", encoding="utf-8")

    monkeypatch.setattr(main_module.settings, "frontend_dist", str(dist))
    test_app = main_module.create_app()

    with TestClient(test_app) as client:
        index_response = client.get("/admin/weeks/1")
        asset_response = client.get("/assets/app-abc123.js")

    assert index_response.status_code == 200
    assert index_response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert index_response.headers["pragma"] == "no-cache"
    assert index_response.headers["expires"] == "0"
    assert asset_response.status_code == 200
    assert asset_response.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize(
    "request_path",
    [
        "/%2e%2e/secret.txt",
        "/..%2fsecret.txt",
        "/%2e%2e%2fsecret.txt",
        "/%2e%2e/%2e%2e/etc/passwd",
    ],
)
def test_spa_route_rejects_path_traversal(tmp_path, monkeypatch, request_path):
    from app import main as main_module

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>app</body></html>", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("outside-dist-secret", encoding="utf-8")

    monkeypatch.setattr(main_module.settings, "frontend_dist", str(dist))
    test_app = main_module.create_app()

    with TestClient(test_app) as client:
        response = client.get(request_path)

    assert response.status_code == 404
    assert "outside-dist-secret" not in response.text

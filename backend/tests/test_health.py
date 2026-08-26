from importlib import import_module
from pathlib import Path

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok():
    main_path = Path("app/main.py")
    assert main_path.exists(), "app/main.py does not exist yet"

    module = import_module("app.main")
    client = TestClient(module.app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

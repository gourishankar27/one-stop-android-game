from fastapi.testclient import TestClient

from one_job.main import create_app


def test_health_contract() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "one-job-server"}


def test_gameplay_transport_is_not_exposed_yet() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/rooms").status_code == 404
        assert "/ws" not in client.get("/openapi.json").json()["paths"]

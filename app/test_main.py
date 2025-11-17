from fastapi.testclient import TestClient
from pathlib import Path
from .main import app
import json
client = TestClient(app)

BASE_DIR = Path(__file__).resolve().parents[1]
PAYLOAD_PATH = BASE_DIR / "example_payloads" / "payload3.json"
EXPECTED_RESPONSE_PATH = BASE_DIR / "example_payloads" / "response3.json"


def test_read_main():
    client = TestClient(app)

    payload = json.loads(PAYLOAD_PATH.read_text())
    expected_response = json.loads(EXPECTED_RESPONSE_PATH.read_text())

    response = client.post("/productionplan", json=payload)

    assert response.status_code == 200
    assert response.json() == expected_response
    
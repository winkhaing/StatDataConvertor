import io
import json

from statdata_converter.cli import _serve
from statdata_converter.service import ConversionService


def test_server_protocol_returns_one_json_response_per_request(monkeypatch) -> None:
    request = json.dumps(
        {"id": 42, "method": "capabilities", "params": {}}
    )
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO(request + "\n"))
    monkeypatch.setattr("sys.stdout", output)

    assert _serve(ConversionService()) == 0
    response = json.loads(output.getvalue())
    assert response["id"] == 42
    assert response["result"]["privacy"]["local_only"] is True


def test_server_protocol_returns_structured_errors(monkeypatch) -> None:
    request = json.dumps({"id": 7, "method": "does-not-exist"})
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO(request + "\n"))
    monkeypatch.setattr("sys.stdout", output)

    _serve(ConversionService())
    response = json.loads(output.getvalue())
    assert response["id"] == 7
    assert "Unknown engine method" in response["error"]


def test_server_protocol_returns_bridge_diagnostics(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("STATDATA_BRIDGE_HOME", str(tmp_path / "bridges"))
    request = json.dumps(
        {"id": 9, "method": "bridge_diagnostics", "params": {}}
    )
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO(request + "\n"))
    monkeypatch.setattr("sys.stdout", output)

    assert _serve(ConversionService()) == 0
    response = json.loads(output.getvalue())
    assert response["id"] == 9
    assert response["result"]["summary"]["installed"] == 0
    assert response["result"]["summary"]["ready"] == 0


def test_server_protocol_routes_certification_audit(monkeypatch) -> None:
    service = ConversionService()
    monkeypatch.setattr(
        service,
        "audit_certification",
        lambda path: {"status": "passed", "manifest_path": path},
    )
    request = json.dumps(
        {
            "id": 11,
            "method": "audit_certification",
            "params": {"manifest_path": "/evidence/certification.json"},
        }
    )
    output = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO(request + "\n"))
    monkeypatch.setattr("sys.stdout", output)

    assert _serve(service) == 0
    response = json.loads(output.getvalue())
    assert response["id"] == 11
    assert response["result"] == {
        "status": "passed",
        "manifest_path": "/evidence/certification.json",
    }

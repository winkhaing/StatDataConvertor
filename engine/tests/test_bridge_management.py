import json
import sys
from pathlib import Path

import pytest
from statdata_converter.bridge_management import install_bridge
from statdata_converter.service import ConversionService

PROBE_SCRIPT = """
import json
import sys

if sys.argv[1] != "probe":
    raise SystemExit(2)
request = json.load(sys.stdin)
print(json.dumps({
    "status": "ok",
    "protocol_version": request["protocol_version"],
    "version": "fixture-1",
    "can_read": True,
    "can_write": True,
}))
"""


def _bundle(root: Path) -> Path:
    root.mkdir()
    (root / "bridge.py").write_text(PROBE_SCRIPT, encoding="utf-8")
    manifest = root / "fixture.statdata-bridge.json"
    manifest.write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "name": "Fixture Bridge",
                "executable": sys.executable,
                "arguments": ["bridge.py"],
                "format": {
                    "id": "fixture",
                    "family": "Fixture",
                    "label": "Fixture data",
                    "extensions": [".fixture"],
                    "can_read": True,
                    "can_write": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_installs_bundle_and_reports_ready_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STATDATA_BRIDGE_HOME", str(tmp_path / "installed"))
    manifest = _bundle(tmp_path / "source")

    result = ConversionService().install_bridge(manifest)

    assert result["status"] == "installed"
    assert result["bridge"]["available"] is True
    assert result["bridge"]["version"] == "fixture-1"
    assert Path(result["manifest_path"]).name == "bridge.json"
    assert result["diagnostics"]["summary"]["ready"] == 1
    capability = next(
        item
        for item in result["capabilities"]["formats"]
        if item["id"] == "fixture"
    )
    assert capability["can_read"] is True
    assert capability["can_write"] is True


def test_refuses_to_replace_existing_bridge(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STATDATA_BRIDGE_HOME", str(tmp_path / "installed"))
    manifest = _bundle(tmp_path / "source")
    install_bridge(manifest)

    with pytest.raises(FileExistsError, match="already installed"):
        install_bridge(manifest)


def test_refuses_symbolic_links_in_bundle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STATDATA_BRIDGE_HOME", str(tmp_path / "installed"))
    manifest = _bundle(tmp_path / "source")
    link = manifest.parent / "outside-link"
    try:
        link.symlink_to(tmp_path / "outside")
    except OSError:
        pytest.skip("Symbolic links are unavailable on this platform.")

    with pytest.raises(ValueError, match="symbolic links"):
        install_bridge(manifest)


def test_refuses_ambiguous_primary_manifests(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("STATDATA_BRIDGE_HOME", str(tmp_path / "installed"))
    manifest = _bundle(tmp_path / "source")
    (manifest.parent / "bridge.json").write_text(
        manifest.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="more than one primary manifest"):
        install_bridge(manifest)

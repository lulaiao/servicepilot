from pathlib import Path

import pytest

from servicepilot.delivery.release_readiness import audit_release_readiness


def _write_minimum_project(root: Path) -> list[str]:
    files = {
        "pyproject.toml": (
            '[project]\nname = "servicepilot"\nversion = "0.1.0"\n'
            'license = {text = "Apache-2.0"}\n'
        ),
        "LICENSE": "Apache License\nVersion 2.0, January 2004\n",
        "README.md": "# ServicePilot\n",
        "CONTRIBUTING.md": "# Contributing\n",
        "SECURITY.md": "# Security policy\n",
        "CHANGELOG.md": "# Changelog\n",
        "docs/release_checklist.md": "# Release checklist\n",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return sorted(files)


def test_release_readiness_accepts_local_only_project(tmp_path: Path) -> None:
    tracked = _write_minimum_project(tmp_path)

    result = audit_release_readiness(tmp_path, tracked)

    assert result.local_readiness_passed is True
    assert result.external_release_authorized is False
    assert result.package_version == "0.1.0"
    assert result.sensitive_filename_matches == ()
    assert result.secret_signature_matches == ()


@pytest.mark.parametrize(
    "unsafe_name",
    [".env", "keys/service.pem", "models/agent.safetensors", "weights/model.pth"],
)
def test_release_readiness_rejects_sensitive_tracked_files(
    tmp_path: Path, unsafe_name: str
) -> None:
    tracked = _write_minimum_project(tmp_path)
    path = tmp_path / unsafe_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")

    result = audit_release_readiness(tmp_path, [*tracked, unsafe_name])

    assert result.local_readiness_passed is False
    assert result.sensitive_filename_matches == (unsafe_name,)


def test_release_readiness_detects_secret_signature_without_exposing_value(
    tmp_path: Path,
) -> None:
    tracked = _write_minimum_project(tmp_path)
    unsafe_name = "config.txt"
    (tmp_path / unsafe_name).write_text(
        "-----BEGIN " + "PRIVATE KEY-----\nredacted\n", encoding="utf-8"
    )

    result = audit_release_readiness(tmp_path, [*tracked, unsafe_name])

    assert result.local_readiness_passed is False
    assert result.secret_signature_matches == (unsafe_name,)


def test_release_readiness_rejects_license_metadata_mismatch(tmp_path: Path) -> None:
    tracked = _write_minimum_project(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "servicepilot"\nversion = "0.1.0"\nlicense = {text = "MIT"}\n',
        encoding="utf-8",
    )

    result = audit_release_readiness(tmp_path, tracked)

    assert result.local_readiness_passed is False
    assert "license_metadata_is_apache_2_0" in result.failed_checks

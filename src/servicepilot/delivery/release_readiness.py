"""Deterministic, non-publishing checks for local release readiness."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

REQUIRED_FILES = (
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "docs/release_checklist.md",
    "pyproject.toml",
)
SENSITIVE_SUFFIXES = frozenset({".bin", ".key", ".pem", ".pt", ".pth", ".safetensors"})
SECRET_SIGNATURES = (
    re.compile(rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
)


@dataclass(frozen=True)
class ReleaseReadiness:
    package_version: str
    required_files_present: bool
    license_metadata_is_apache_2_0: bool
    license_text_is_apache_2_0: bool
    sensitive_filename_matches: tuple[str, ...]
    secret_signature_matches: tuple[str, ...]
    failed_checks: tuple[str, ...]
    local_readiness_passed: bool
    external_release_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_sensitive_filename(value: str) -> bool:
    path = PurePosixPath(value)
    return path.name == ".env" or path.suffix.lower() in SENSITIVE_SUFFIXES


def audit_release_readiness(root: Path, tracked_paths: Iterable[str]) -> ReleaseReadiness:
    """Audit tracked repository inputs without modifying or publishing anything."""
    normalized_paths = tuple(sorted(set(tracked_paths)))
    missing = tuple(name for name in REQUIRED_FILES if not (root / name).is_file())
    pyproject_path = root / "pyproject.toml"
    project: dict[str, Any] = {}
    package_version = "TBD"
    if pyproject_path.is_file():
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = pyproject.get("project", {})
        package_version = str(project.get("version", "TBD"))
        if package_version == "TBD" and "version" in project.get("dynamic", []):
            version_path = root / "src/servicepilot/_version.py"
            if version_path.is_file():
                match = re.search(
                    r'^__version__\s*=\s*["\']([^"\']+)["\']',
                    version_path.read_text(encoding="utf-8"),
                    re.MULTILINE,
                )
                if match:
                    package_version = match.group(1)
    license_value = project.get("license")
    license_text = license_value.get("text") if isinstance(license_value, dict) else license_value
    metadata_ok = license_text == "Apache-2.0"
    license_body = (
        (root / "LICENSE").read_text(encoding="utf-8")
        if (root / "LICENSE").is_file()
        else ""
    )
    body_ok = "Apache License" in license_body and "Version 2.0" in license_body
    sensitive = tuple(value for value in normalized_paths if _is_sensitive_filename(value))
    signature_matches = []
    for value in normalized_paths:
        path = root / value
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        content = path.read_bytes()
        if any(pattern.search(content) for pattern in SECRET_SIGNATURES):
            signature_matches.append(value)
    checks = {
        "required_files_present": not missing,
        "license_metadata_is_apache_2_0": metadata_ok,
        "license_text_is_apache_2_0": body_ok,
        "no_sensitive_tracked_filenames": not sensitive,
        "no_tracked_secret_signatures": not signature_matches,
    }
    failed = tuple(name for name, passed in checks.items() if not passed)
    return ReleaseReadiness(
        package_version=package_version,
        required_files_present=not missing,
        license_metadata_is_apache_2_0=metadata_ok,
        license_text_is_apache_2_0=body_ok,
        sensitive_filename_matches=sensitive,
        secret_signature_matches=tuple(signature_matches),
        failed_checks=failed,
        local_readiness_passed=not failed,
    )

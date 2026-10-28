"""Explicit DeepSeek credential loading with no secret exposure.

The selected source for this run is ``credentials/deepseek.env``.  The file is
parsed explicitly; a generic ``.env`` search would be ambiguous and is not used.
Reports expose only presence, length bucket, variable name, and problem type.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class CredentialError(RuntimeError):
    """Credential file is missing, ambiguous, or not usable."""


@dataclass(frozen=True)
class CredentialReport:
    """Public, secret-free description of the selected credential source."""

    path: str
    variable: str
    key_present: bool
    key_length: int
    environment_present: bool
    environment_conflict: bool
    warnings: tuple[str, ...]

    def public_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "variable": self.variable,
            "key_present": self.key_present,
            "key_length": self.key_length,
            "environment_present": self.environment_present,
            "environment_conflict": self.environment_conflict,
            "warnings": list(self.warnings),
        }


def _parse_dotenv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise CredentialError(
                f"{line_number}: non-comment line has no '='; expected VARIABLE=value"
            )
        name, raw_value = line.split("=", 1)
        name = name.strip()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if not name or any(character.isspace() for character in name):
            raise CredentialError(f"{line_number}: invalid variable name")
        if name in values:
            raise CredentialError(f"{line_number}: duplicate variable {name}")
        values[name] = value
    return values


def load_secret(
    path: Path | str,
    variable: str,
    *,
    allowed_prefixes: tuple[str, ...] = (),
) -> tuple[str, CredentialReport]:
    """Load a vendor key from an explicit dotenv or single-line file.

    The file content is never printed.  Plain one-line files are accepted for
    vendor keys that are not dotenv-formatted; no ambient dotenv search occurs.
    """

    credential_path = Path(path)
    if not credential_path.exists():
        raise CredentialError(f"credential file not found: {credential_path}")
    if not credential_path.is_file():
        raise CredentialError(f"credential path is not a file: {credential_path}")
    try:
        text = credential_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CredentialError(f"credential file unreadable: {type(error).__name__}") from error

    non_comment = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    values: dict[str, str] = {}
    if any("=" in line for line in non_comment):
        values = _parse_dotenv(text)
        key = values.get(variable, "")
        if not key:
            known = ", ".join(sorted(values)) or "none"
            raise CredentialError(
                f"{variable} is missing from {credential_path}; present variable names: {known}"
            )
    elif len(non_comment) == 1:
        key = non_comment[0]
    else:
        raise CredentialError(
            f"{credential_path} must contain one key line or VARIABLE=value entries"
        )

    if any(character.isspace() for character in key):
        raise CredentialError("credential value contains whitespace")
    if not key.isascii():
        raise CredentialError("credential value is not ASCII")
    if len(key) < 20:
        raise CredentialError("credential value is implausibly short")

    warnings: list[str] = []
    if allowed_prefixes and not key.startswith(allowed_prefixes):
        warnings.append(f"value does not start with an expected prefix {allowed_prefixes}")
    environment_key = os.environ.get(variable, "")
    environment_conflict = bool(environment_key and environment_key != key)
    if environment_conflict:
        warnings.append(
            "process environment contains a different value; the explicit credential file takes precedence"
        )
    report = CredentialReport(
        path=str(credential_path),
        variable=variable,
        key_present=True,
        key_length=len(key),
        environment_present=bool(environment_key),
        environment_conflict=environment_conflict,
        warnings=tuple(warnings),
    )
    return key, report


def load_deepseek_key(
    path: Path | str = Path("credentials/deepseek.env"),
    variable: str = "DEEPSEEK_API_KEY",
) -> tuple[str, CredentialReport]:
    """Load ``variable`` from ``path`` and return the key plus a safe report.

    Precedence is explicit: the file is the selected source.  If the process
    environment contains a different value, the report records a conflict and
    the file value is still used; no value is printed or logged.
    """

    credential_path = Path(path)
    if not credential_path.exists():
        raise CredentialError(f"credential file not found: {credential_path}")
    if not credential_path.is_file():
        raise CredentialError(f"credential path is not a file: {credential_path}")

    try:
        text = credential_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CredentialError(f"credential file unreadable: {type(error).__name__}") from error

    values = _parse_dotenv(text)
    key = values.get(variable, "")
    warnings: list[str] = []
    if not key:
        known = ", ".join(sorted(values)) or "none"
        raise CredentialError(
            f"{variable} is missing from {credential_path}; present variable names: {known}"
        )
    if any(character.isspace() for character in key):
        raise CredentialError("credential value contains whitespace")
    if not key.isascii():
        raise CredentialError("credential value is not ASCII")
    if len(key) < 20:
        raise CredentialError("credential value is implausibly short")
    if not key.startswith("sk-"):
        warnings.append("value does not start with 'sk-'; loader accepts it but the vendor may reject it")

    environment_key = os.environ.get(variable, "")
    environment_conflict = bool(environment_key and environment_key != key)
    if environment_conflict:
        warnings.append(
            "process environment contains a different value; the explicit credential file takes precedence"
        )

    report = CredentialReport(
        path=str(credential_path),
        variable=variable,
        key_present=True,
        key_length=len(key),
        environment_present=bool(environment_key),
        environment_conflict=environment_conflict,
        warnings=tuple(warnings),
    )
    return key, report

"""Claims read from one acquired metadata file.

A claim is copied only when it is ASCII text with no credential, query or fragment. A second claim
for the same field is kept when it agrees and recorded as a conflict when it does not.
"""

import re
from urllib.parse import urlsplit

MAX_METADATA_BYTES = 1024 * 1024
_SECRET = re.compile(
    r"(?i)(hf_[A-Za-z0-9]{12,}|bearer\s+\S+|(?:token|password|secret|api[_-]?key)\s*[=:]\s*\S+)"
)


class Evidence:
    """Metadata claims for one video. A conflict leaves the disagreed fields empty."""

    def __init__(
        self,
        source_reference: str | None,
        annotation_reference: str | None,
        license_name: str | None,
        license_reference: str | None,
        metadata_sha256: str | None,
        association: str,
        conflicted: frozenset[str] = frozenset(),
    ) -> None:
        self.source_reference = source_reference
        self.annotation_reference = annotation_reference
        self.license_name = license_name
        self.license_reference = license_reference
        self.metadata_sha256 = metadata_sha256
        self.association = association
        self.conflicted = conflicted

    @staticmethod
    def missing() -> "Evidence":
        """Return the claims of a video no metadata file named."""
        return Evidence(None, None, None, None, None, "missing")


class Unresolved:
    """One metadata file or line that was not joined, or one pair of disagreeing claims."""

    def __init__(self, kind: str, path: str, detail: str) -> None:
        self.kind = kind
        self.path = path
        self.detail = detail

    def to_record(self) -> dict[str, str]:
        """Return the sealed-record object."""
        return {"kind": self.kind, "path": self.path, "detail": self.detail}


class _Claim:
    def __init__(self, value: str, source: str, digest: str | None) -> None:
        self.value = value
        self.source = source
        self.digest = digest


class Claims:
    """The claims one or more files made about a single video."""

    def __init__(self) -> None:
        self._fields: dict[str, _Claim] = {}
        self.conflicts: list[tuple[str, str]] = []
        self.seen = False

    def add(self, field: str, value: str, source: str, digest: str | None, video: str) -> None:
        """Record one evidenced value, or a conflict when an earlier value disagrees."""
        self.seen = True
        found = self._fields.get(field)
        if found is None:
            self._fields[field] = _Claim(value, source, digest)
            return
        if found.value != value:
            detail = f"{video} {field} {found.source}={found.value} {source}={value}"
            self.conflicts.append((field, detail))

    def evidence(self) -> Evidence:
        """Return the claims that did not conflict."""
        conflicted = frozenset(name for name, _detail in self.conflicts)
        if conflicted:
            association = "conflict"
        elif self.seen:
            association = "matched"
        else:
            association = "missing"
        return Evidence(
            self._value("source_reference"),
            self._value("annotation_reference"),
            self._value("license"),
            None if "license" in conflicted else self._source("license"),
            None if conflicted else self._digest(),
            association,
            conflicted,
        )

    def _conflicted(self, field: str) -> bool:
        return any(name == field for name, _detail in self.conflicts)

    def _value(self, field: str) -> str | None:
        if self._conflicted(field):
            return None
        claim = self._fields.get(field)
        return None if claim is None else claim.value

    def _source(self, field: str) -> str | None:
        claim = self._fields.get(field)
        return None if claim is None else claim.source

    def _digest(self) -> str | None:
        for claim in self._fields.values():
            if claim.digest is not None:
                return claim.digest
        return None


def bucket(found: dict[str, Claims], video: str) -> Claims:
    """Return the claim set for one video, creating it and marking the video named."""
    claims = found.get(video)
    if claims is None:
        claims = Claims()
        found[video] = claims
    claims.seen = True
    return claims


def usable(value: object) -> str | None:
    """Return ASCII text that carries no credential, query or fragment, else nothing."""
    if not isinstance(value, str) or not value.strip() or not value.isascii():
        return None
    if _SECRET.search(value):
        return None
    if "://" not in value:
        return value
    return _url(value)


def _url(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        return None
    return value

"""What the registry states: a contract, its frozen versions, their identity and its vocabulary.

Nothing here reads a file. `schema.registry.store` loads the set and checks each file against these pins.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ss_track.core.refusal import JsonValue

KIND_FIELD = "kind"
VERSION_FIELD = "schema_version"
RECORD_FAMILY = "record"
DECLARATION_FAMILY = "declaration"
SHARED_FAMILY = "shared"
INITIAL = "initial"  # the change classes a registry entry states, from meta/registry.json
PATCH = "patch"
MINOR = "minor"
MAJOR = "major"
VIEW = "view"
FACTS = "facts"
RETIRED = "retired"
DISPOSITIONS = (VIEW, FACTS, RETIRED)  # from most to least usable, so the strictest step wins
_URN_PREFIX = "urn:ss-track:contract"


def contract_urn(family: str, contract_id: str, version: str) -> str:
    """Return the stable identity of one frozen version."""
    return f"{_URN_PREFIX}:{family}:{contract_id}:{version}"


def version_path(name: str, version: str) -> Path:
    """Return where one frozen version of `<family>/<id>` sits, relative to the set's root."""
    return Path(*name.split("/"), f"{version}.json")


def version_key(version: str) -> tuple[int, ...]:
    """Return a version as numbers, because `10.0.0` sorts after `9.0.0`."""
    return tuple(int(part) for part in version.split("."))


@dataclass(frozen=True, slots=True)
class FrozenVersion:
    """One immutable version as the registry pins it."""

    version: str
    file_sha256: str
    structure: str
    meaning: str
    change: Mapping[str, JsonValue]

    @property
    def major(self) -> int:
        return version_key(self.version)[0]


@dataclass(frozen=True, slots=True)
class Contract:
    """One registry entry: a format and every frozen version of it, oldest first."""

    family: str
    contract_id: str
    owner: str
    status: str
    description: str
    reason: str | None
    versions: tuple[FrozenVersion, ...]
    retired_majors: tuple[Mapping[str, JsonValue], ...] = ()

    @property
    def name(self) -> str:
        return f"{self.family}/{self.contract_id}"

    def urn(self, frozen: FrozenVersion) -> str:
        return contract_urn(self.family, self.contract_id, frozen.version)

    def relative_path(self, frozen: FrozenVersion) -> Path:
        return version_path(self.name, frozen.version)

    def newest(self, major: int | None = None) -> FrozenVersion | None:
        """Return the newest frozen version, of one major when given, which reads all its minors."""
        found = [item for item in self.versions if major is None or item.major == major]
        return max(found, key=lambda item: version_key(item.version), default=None)

    def migration_from(self, major: int) -> str | None:
        """Return the change log's migration for a holder of a record of an earlier major.

        A retired major states its own. Otherwise it is the first major transition after it, which
        the gate requires to carry migration text.
        """
        for entry in self.retired_majors:
            if entry["major"] == major:
                return str(entry["migration"])
        for frozen in self.versions:
            if frozen.major > major and frozen.change["class"] == MAJOR:
                return str(frozen.change["migration"])
        return None

    def disposition_of(self, major: int) -> str | None:
        """Return how a record of an earlier major is read, as one change-log entry states it.

        A historic major with no frozen contract states its own. Otherwise the major transition that
        replaced it declared it. A major that neither names, which no version wrote, has none.
        """
        for entry in self.retired_majors:
            if entry["major"] == major:
                return str(entry["status"])
        for frozen in self.versions:
            if frozen.major == major + 1 and frozen.change["class"] == MAJOR:
                return str(frozen.change["disposition"])
        return None

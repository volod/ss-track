"""Strict reading of operator-written YAML, with no silent defaults or ignored keys."""

import math
import re
from collections.abc import Collection, Hashable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import TracebackType
from typing import Self

import yaml

from ss_track.corpus.refusal import CorpusRefusal, RefusalCode

SCHEMA_VERSION = 1
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
IDENTIFIER_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


@dataclass(frozen=True, slots=True)
class Selection:
    """A half-open frame window `[start_frame, end_frame)` over one sequence."""

    start_frame: int
    end_frame: int


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe loader that refuses a repeated key, which PyYAML would silently overwrite."""

    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[Hashable, object]:
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if isinstance(key, Hashable) and key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark
                )
            if isinstance(key, Hashable):
                seen.add(key)
        return super().construct_mapping(node, deep)


def invalid(message: str) -> CorpusRefusal:
    """Build the refusal for a malformed operator declaration."""
    return CorpusRefusal(RefusalCode.MANIFEST_INVALID, message)


def load_yaml_mapping(path: Path) -> object:
    """Parse one YAML file, reporting any read or syntax failure as a refusal."""
    try:
        text = path.read_text(encoding="utf-8")
        return yaml.load(text, Loader=_UniqueKeyLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise invalid(f"cannot read {path.name}: {error}") from error


class Fields:
    """Read one mapping once; closing it refuses any key that was never read."""

    def __init__(self, raw: object, where: str) -> None:
        if not isinstance(raw, dict):
            raise invalid(f"{where} must be a mapping")
        self._raw: dict[object, object] = dict(raw)
        self._where = where

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if kind is None:
            self.close()

    def close(self) -> None:
        """Refuse keys the schema does not define, so a misspelling cannot vanish."""
        if self._raw:
            names = sorted(str(key) for key in self._raw)
            raise invalid(f"{self._where} has unknown fields: {', '.join(names)}")

    @property
    def where(self) -> str:
        """Return this mapping's place in its declaration, for a refusal message."""
        return self._where

    def has(self, key: str) -> bool:
        return key in self._raw

    def _take(self, key: str) -> object:
        if key not in self._raw:
            raise invalid(f"{self._where}.{key} is required")
        return self._raw.pop(key)

    def text(self, key: str) -> str:
        """Read a required, non-blank string."""
        value = self._take(key)
        if not isinstance(value, str) or not value.strip():
            raise invalid(f"{self._where}.{key} must be a non-empty string")
        return value

    def boolean(self, key: str) -> bool:
        """Read an explicit boolean, never a number or string."""
        value = self._take(key)
        if not isinstance(value, bool):
            raise invalid(f"{self._where}.{key} must be a boolean")
        return value

    def nullable_date(self, key: str) -> str | None:
        """Read a required ISO calendar date or explicit null for no end."""
        value = self._take(key)
        if value is None:
            return None
        if type(value) is date:
            return value.isoformat()
        if isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
                if parsed.isoformat() == value:
                    return value
            except ValueError:
                pass
        raise invalid(f"{self._where}.{key} must be YYYY-MM-DD or null")

    def optional_text(self, key: str) -> str | None:
        return self.text(key) if self.has(key) else None

    def identifier(self, key: str) -> str:
        """Read a required name that is safe in a path and stable in a record."""
        value = self.text(key)
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise invalid(f"{key} must match {IDENTIFIER_PATTERN.pattern}")
        return value

    def choice(self, key: str, allowed: Collection[str]) -> str:
        """Read a string limited to a closed vocabulary."""
        value = self.text(key)
        if value not in allowed:
            options = ", ".join(sorted(allowed))
            raise invalid(f"{self._where}.{key} must be one of: {options}")
        return value

    def index(self, key: str) -> int:
        """Read a required non-negative integer; a YAML boolean is not one."""
        value = self._take(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise invalid(f"{self._where}.{key} must be a non-negative integer")
        return value

    def sha256(self, key: str) -> str:
        """Read a required lowercase SHA-256 digest."""
        value = self.text(key)
        if not SHA256_PATTERN.fullmatch(value):
            raise invalid(f"{self._where}.{key} must be 64 lowercase hex characters")
        return value

    def scalar(self, key: str) -> str | int | float | None:
        """Read an optional descriptive value, keeping an absent one as unknown."""
        if not self.has(key):
            return None
        value = self._take(key)
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            raise invalid(f"{self._where}.{key} must be a string or a number")
        if isinstance(value, float) and not math.isfinite(value):
            raise invalid(f"{self._where}.{key} must be a finite number")
        return value

    def child(self, key: str) -> "Fields":
        """Read a required nested mapping."""
        return Fields(self._take(key), f"{self._where}.{key}")

    def optional_child(self, key: str) -> "Fields":
        """Read a nested mapping, treating an absent one as empty."""
        return Fields(self._raw.pop(key, {}), f"{self._where}.{key}")

    def items(self, key: str) -> list[object]:
        """Read a required, non-empty list."""
        value = self._take(key)
        if not isinstance(value, list) or not value:
            raise invalid(f"{self._where}.{key} must be a non-empty list")
        return value

    def selection(self, key: str) -> Selection:
        """Read a required, non-empty frame window."""
        with self.child(key) as window:
            selection = Selection(window.index("start_frame"), window.index("end_frame"))
        if selection.start_frame >= selection.end_frame:
            raise invalid(f"{self._where}.{key} must have start_frame before end_frame")
        return selection

    def schema_version(self, expected: int = SCHEMA_VERSION) -> None:
        """Refuse any declaration written for another schema."""
        version = self._take("schema_version")
        if type(version) is not int or version != expected:
            raise invalid(f"{self._where}.schema_version must be {expected}")

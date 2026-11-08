"""Typed access to an operator declaration that its contract has already validated.

The contract states every structural rule: keys, types, vocabularies, bounds and patterns, and the
validator refuses a value YAML read as a date wherever text belongs. What is left here is typing,
defaults and the rules the dialect cannot state, which each contract names under `x-rules`: a frame
window's order and free text holding a character other than whitespace (`TEXT_RULE`).
"""

from dataclasses import dataclass
from typing import cast

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode

TEXT_RULE = "text"  # the `x-rules` name of the not-blank rule, on each free-text property
type _Scalar = str | int | float


@dataclass(frozen=True, slots=True)
class Selection:
    """A half-open frame window `[start_frame, end_frame)` over one sequence."""

    start_frame: int
    end_frame: int


def invalid(message: str) -> CorpusRefusal:
    """Build the refusal for a malformed operator declaration."""
    return CorpusRefusal(RefusalCode.MANIFEST_INVALID, message)


class Fields:
    """Read one validated mapping. A type its contract did not promise is a defect of this code."""

    def __init__(self, raw: object, where: str) -> None:
        if not isinstance(raw, dict):
            raise TypeError(f"{where} is not a mapping: its contract and reader disagree")
        self._raw: dict[str, object] = raw
        self._where = where

    @property
    def where(self) -> str:
        """Return this mapping's place in its declaration, for a refusal message."""
        return self._where

    def has(self, key: str) -> bool:
        return key in self._raw

    def _get[T](self, key: str, kind: type[T] | tuple[type, ...]) -> T:
        value = self._raw[key]
        if (isinstance(value, bool) and kind is not bool) or not isinstance(value, kind):
            raise TypeError(f"{self._where}.{key} is not {kind}: its contract and reader disagree")
        return cast(T, value)

    def text(self, key: str) -> str:
        """Read a required string, refusing one that is only whitespace: the `text` rule."""
        value = self._get(key, str)
        if not value.strip():
            raise invalid(f"{self._where}.{key} must not be blank")
        return value

    def optional_text(self, key: str) -> str | None:
        return self.text(key) if self.has(key) else None

    def nullable_text(self, key: str) -> str | None:
        """Read a required string or an explicit null, refusing text that is only whitespace."""
        if self._raw[key] is None:
            return None
        return self.text(key)

    def nullable_date(self, key: str) -> str | None:
        """Read a required ISO date, quoted or as YAML wrote it, or an explicit null."""
        value = self._raw[key]
        return None if value is None else str(self._get(key, str))

    def boolean(self, key: str) -> bool:
        return self._get(key, bool)

    def index(self, key: str) -> int:
        return self._get(key, int)

    def scalar(self, key: str) -> _Scalar | None:
        """Read an optional descriptive value, keeping an absent one as unknown."""
        return cast(_Scalar, self._get(key, (str, int, float))) if self.has(key) else None

    def child(self, key: str) -> "Fields":
        return Fields(self._raw[key], f"{self._where}.{key}")

    def optional_child(self, key: str) -> "Fields":
        """Read a nested mapping, treating an absent one as empty."""
        return Fields(self._raw.get(key, {}), f"{self._where}.{key}")

    def items(self, key: str) -> list[object]:
        return self._get(key, list)

    def optional_items(self, key: str) -> list[object]:
        return self.items(key) if self.has(key) else []

    def mapping(self, key: str) -> dict[str, JsonValue]:
        """Read a nested mapping whole, as the contract stated every value in it."""
        return cast(dict[str, JsonValue], self._get(key, dict))

    def selection(self, key: str) -> Selection:
        """Read a frame window, which must be non-empty: a rule across its two fields."""
        window = self.child(key)
        selection = Selection(window.index("start_frame"), window.index("end_frame"))
        if selection.start_frame >= selection.end_frame:
            raise invalid(f"{self._where}.{key} must have start_frame before end_frame")
        return selection

    def optional_selection(self, key: str) -> Selection | None:
        return self.selection(key) if self.has(key) else None

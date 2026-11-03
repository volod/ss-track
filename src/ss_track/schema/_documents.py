"""Strict document parsing for explicit contract validation."""

import json
import math
from datetime import date
from pathlib import Path

import yaml

from ss_track.refusal import CorpusRefusal, RefusalCode
from ss_track.strict_json import finite_float, reject_constant, unique_object
from ss_track.strict_yaml import UniqueKeyLoader


def _mapping(value: dict[object, object]) -> dict[str, object]:
    if any(not isinstance(key, str) for key in value):
        raise ValueError("mapping keys must be strings")
    return {str(key): _normalize(child) for key, child in value.items()}


def _normalize(value: object) -> object:
    """Keep YAML in the JSON data model, normalizing unquoted calendar dates."""
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, dict):
        return _mapping(value)
    if isinstance(value, list):
        return [_normalize(child) for child in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite numbers are not JSON")
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise ValueError(f"{type(value).__name__} is not a JSON value")


def _read_document(path: Path, *, declaration: bool = False) -> object:
    """Read declaration YAML or strict JSON, with the family's refusal code."""
    code = RefusalCode.MANIFEST_INVALID if declaration else RefusalCode.RECORD_INVALID
    encoding = "YAML" if declaration else "JSON"
    try:
        payload = path.read_text(encoding="utf-8")
        if declaration:
            return _normalize(yaml.load(payload, Loader=UniqueKeyLoader))
        return _normalize(
            json.loads(
                payload,
                object_pairs_hook=unique_object,
                parse_constant=reject_constant,
                parse_float=finite_float,
            )
        )
    except (ValueError, RecursionError, yaml.YAMLError) as error:
        raise CorpusRefusal(code, f"{path.name} is not valid {encoding}: {error}") from error

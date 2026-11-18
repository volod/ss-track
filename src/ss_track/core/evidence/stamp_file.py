"""The bytes of `contract-set.json`, the one file of a development data root that is not a record.

What the stamp means and when it is checked or written is `core.evidence.contract_stamp`.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.core.strict_json import reject_constant, unique_object

STAMP_NAME = "contract-set.json"
STAMP_KIND = "ss-track.development-contract-set"
REGENERATE_REMEDY = (
    "this data root may have been written under an earlier development contract set: delete its sealed "
    "datasets and the stamp, keep operator-written declarations, labels and review decisions, and "
    "regenerate the datasets from them with this ss-track (spec section 17.7)"
)


def read_stamp(
    path: Path,
) -> tuple[Mapping[str, str], Mapping[str, str] | None] | None:
    """Parse the stamp, the one file of a data root that is not a sealed record."""
    try:
        text = path.read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    except UnicodeError as error:
        raise _damaged(path, f"not ASCII: {error}") from error
    try:
        document = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, RecursionError) as error:
        raise _damaged(path, f"not JSON: {error}") from error
    if not isinstance(document, dict) or document.get("kind") != STAMP_KIND:
        raise _damaged(path, "not a development contract-set stamp")
    contracts = _fingerprint_map(path, document.get("contracts"))
    raw_meanings = document.get("meanings")
    meanings = (
        None
        if raw_meanings is None and "meanings" not in document
        else _fingerprint_map(path, raw_meanings)
    )
    return contracts, meanings


def _fingerprint_map(path: Path, value: object) -> dict[str, str]:
    if not isinstance(value, dict) or any(
        not isinstance(name, str)
        or not name.startswith(("record/", "shared/"))
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        for name, digest in value.items()
    ):
        raise _damaged(path, "invalid contract fingerprints")
    return value


def write_stamp(path: Path, installed: Mapping[str, str], meanings: Mapping[str, str]) -> None:
    document = {
        "kind": STAMP_KIND,
        "contracts": dict(sorted(installed.items())),
        "meanings": dict(sorted(meanings.items())),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, (json.dumps(document, indent=2) + "\n").encode("ascii"))


def _damaged(path: Path, reason: str) -> CorpusRefusal:
    return CorpusRefusal(
        RefusalCode.RECORD_TAMPERED,
        f"{path.name} is damaged: {reason}",
        {"stamp": str(path), "remedy": REGENERATE_REMEDY},
    )

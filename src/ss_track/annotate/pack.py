"""Load one scenario pack and the hash of its validated declaration."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from ss_track.annotate.pack_model import ScenarioPack
from ss_track.annotate.pack_read import read_pack
from ss_track.annotate.pack_rules import check_scenario_pack
from ss_track.core.canonical import canonical_json, sha256_bytes
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import Fields
from ss_track.schema.validation.enforce import read_declaration

SCENARIO_PACK_CONTRACT = "declaration/scenario-pack"
SCENARIO_PACK_SCHEMA_VERSION = 1


def load_scenario_pack(path: Path) -> ScenarioPack:
    """Validate one scenario pack and return it with one hash of that document.

    The hash is the SHA-256 of the canonical JSON of the validated declaration.
    Object key order and comments do not change it. Array order does. Changing a
    class, role, extent or bin changes it.
    """
    document = read_declaration(path, SCENARIO_PACK_CONTRACT, SCENARIO_PACK_SCHEMA_VERSION)
    pack = read_pack(Fields(document, path.name), _digest(document))
    check_scenario_pack(pack)
    return pack


def _digest(document: dict[str, Any]) -> str:
    body = cast(Mapping[str, JsonValue], document)
    return sha256_bytes(canonical_json(body))

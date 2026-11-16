"""Load one scenario pack and the hash of its validated declaration."""

from pathlib import Path

from ss_track.annotate.declarations.contracts import SCENARIO_PACK_CONTRACT, read_hashed
from ss_track.annotate.packs.model import ScenarioPack
from ss_track.annotate.packs.read import read_pack
from ss_track.annotate.packs.rules import check_scenario_pack
from ss_track.corpus.declarations.fields import Fields


def load_scenario_pack(path: Path) -> ScenarioPack:
    """Validate one scenario pack and return it with one hash of that document.

    The hash is the SHA-256 of the canonical JSON of the validated declaration.
    Object key order and comments do not change it. Array order does. Changing a
    class, role, extent or bin changes it.
    """
    document, pack_hash = read_hashed(path, SCENARIO_PACK_CONTRACT)
    pack = read_pack(Fields(document, path.name), pack_hash)
    check_scenario_pack(pack)
    return pack

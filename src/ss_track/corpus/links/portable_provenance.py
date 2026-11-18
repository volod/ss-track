"""Bind a development handoff to the contract set its exporting data root was written under.

The pins and their check are `core.evidence.carried_pins`, shared with another host's staged
hashes; this states what a handoff's refusal says and how to recover from it (spec section 17.7).
"""

from collections.abc import Mapping

from ss_track.core.evidence.carried_pins import require_carried_contract_set
from ss_track.core.refusal import JsonValue

MANIFEST_NAME = "manifest.json"
HANDOFF_REMEDY = (
    "export and open the handoff with ss-track versions that install the same contract set: "
    "regenerate the exporting data root under the receiver's contract set and export again, or open "
    "it with the ss-track that exported it (spec section 17.7)"
)


def require_matching_contract_set(manifest: Mapping[str, JsonValue]) -> None:
    """Refuse a development handoff whose contract pins are absent or differ from this install."""
    require_carried_contract_set(
        manifest, carrier="the review handoff", name=MANIFEST_NAME, remedy=HANDOFF_REMEDY
    )

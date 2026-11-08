"""Sealed source records bind collection membership, and a gap stays unbound."""

from pathlib import Path

from ss_track.corpus import import_source
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.evaluation.domains import CollectionId
from ss_track.corpus.evaluation.membership import (
    DISAGREE,
    NO_ORIGIN,
    UNAVAILABLE,
    UNNAMED,
    BoundStream,
    bind_membership,
    paired_membership,
)
from tests.corpus._media import WIDTH, write_clip
from tests.corpus.conftest import WriteRecording

_ORIGIN = {
    "provider": "huggingface",
    "collection_id": "owner/dataset",
    "provider_version": "a" * 40,
    "video_path": "videos/clip.mkv",
    "content_sha256": "a" * 64,
    "upstream_split": None,
    "source_reference": None,
    "annotation_reference": None,
    "attribution": "Fixture Operator",
    "terms": "fixture terms",
    "terms_reference": "https://example.com/terms",
    "license": None,
    "license_reference": None,
    "metadata_sha256": None,
}


def _records(**inventories: dict[str, object]) -> DiscoveryRecords:
    return DiscoveryRecords({"run_id": "run"}, inventories)


def test_membership_follows_the_sealed_origin_and_reports_every_gap(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_clip(media / "one.mkv")
    write_clip(media / "two.mkv", width=WIDTH + 4)
    recorded = import_source(write_recording("one.mkv", origin=[_ORIGIN]), data_root)
    plain = import_source(write_recording("two.mkv"), data_root)
    bound = bind_membership(
        _records(
            one={
                "source_sha256": recorded.source_sha256,
                "source_manifest_sha256": recorded.manifest_sha256,
            },
            two={
                "source_sha256": plain.source_sha256,
                "source_manifest_sha256": plain.manifest_sha256,
            },
            gone={
                "source_sha256": recorded.source_sha256,
                "source_manifest_sha256": "b" * 64,
            },
            blank={},
        ),
        data_root,
    )

    assert bound["one"].reason is None
    assert bound["one"].collections == (CollectionId("huggingface", "owner/dataset"),)
    assert bound["two"].reason == NO_ORIGIN
    assert bound["two"].collections == ()
    assert bound["gone"].reason == UNAVAILABLE
    assert bound["blank"].reason == UNNAMED


def test_two_origins_stay_distinct_and_a_disagreement_drops_both(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_clip(media / "one.mkv")
    write_clip(media / "two.mkv", width=WIDTH + 5)
    other = dict(_ORIGIN)
    other["collection_id"] = "owner/other"
    recorded = import_source(write_recording("one.mkv", origin=[_ORIGIN, other]), data_root)
    plain = import_source(write_recording("two.mkv"), data_root)
    left = _records(
        one={
            "source_sha256": recorded.source_sha256,
            "source_manifest_sha256": recorded.manifest_sha256,
        },
    )
    right = _records(
        one={
            "source_sha256": plain.source_sha256,
            "source_manifest_sha256": plain.manifest_sha256,
        },
    )

    bound = bind_membership(left, data_root)
    assert bound["one"].collections == (
        CollectionId("huggingface", "owner/dataset"),
        CollectionId("huggingface", "owner/other"),
    )
    merged = paired_membership(left, right, data_root)
    assert merged["one"] == BoundStream((), DISAGREE)
    assert paired_membership(left, left, data_root)["one"] == bound["one"]

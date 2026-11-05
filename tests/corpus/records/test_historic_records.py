"""Every kept record is intact, listed, and read by the read path under its disposition."""

import json
from pathlib import Path

import pytest

from ss_track.corpus import open_frame_bundle
from ss_track.corpus.bundles.frame_set import FRAME_SET
from ss_track.corpus.hosts.host_hashes import read_staged_hashes
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.projections import installed_projections
from ss_track.corpus.records.read_window import check_view, installed_views
from ss_track.corpus.records.sealed import read_comparable, read_sealed
from ss_track.corpus.sources.importer import SOURCE_MANIFEST
from ss_track.corpus.versions.builder import CORPUS_MANIFEST
from ss_track.schema.validation.enforce import older_remedy
from tests.corpus._historic import (
    KEPT_FORMATS,
    KEPT_NAMES,
    RECORDS,
    format_of,
    major_of,
    place_record,
)


@pytest.mark.parametrize("name", KEPT_NAMES)
def test_a_kept_record_is_intact_named_for_what_it_holds_and_listed(name: str) -> None:
    major = major_of(name)

    record = read_comparable(RECORDS / name, format_of(name))

    assert record.major == major
    assert name in (RECORDS / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("record_format", KEPT_FORMATS.values(), ids=KEPT_FORMATS.keys())
def test_every_major_of_every_format_keeps_a_real_record(record_format: RecordFormat) -> None:
    majors = {major_of(name) for name in KEPT_NAMES if format_of(name) is record_format}

    assert majors == set(range(1, record_format.major + 1))


def test_records_at_the_current_major_still_open() -> None:
    assert read_staged_hashes(RECORDS / "staged-hashes-schema-1-0bf3b9e.json")
    assert read_sealed(RECORDS / "frame-set-schema-1-fd982a1.json", FRAME_SET)
    assert read_sealed(RECORDS / "source-schema-2-129a350.json", SOURCE_MANIFEST)
    assert read_sealed(RECORDS / "corpus-schema-3-129a350.json", CORPUS_MANIFEST)


def test_a_real_bundle_at_the_current_major_opens(tmp_path: Path) -> None:
    place_record("bundle-schema-3-d6b704d.json", tmp_path / "one" / "manifest.json")

    assert open_frame_bundle(tmp_path / "one").stream_id == "one"


@pytest.mark.parametrize("major", [1, 2])
def test_the_remedy_of_an_older_corpus_names_it_in_supersedes(major: int) -> None:
    remedy = str(older_remedy(CORPUS_MANIFEST.kind, major))

    assert "names this one in supersedes" in remedy
    assert ("not_compared" in remedy) is (major == 1)


@pytest.mark.parametrize(
    "record_format",
    [record_format for record_format in KEPT_FORMATS.values() if record_format.major > 1],
    ids=lambda record_format: record_format.kind,
)
def test_every_older_major_of_a_current_format_has_a_migration(
    record_format: RecordFormat,
) -> None:
    for major in range(1, record_format.major):
        assert older_remedy(record_format.kind, major)


_PROJECTED = sorted(installed_projections(), key=str)


@pytest.mark.parametrize(("kind", "major"), _PROJECTED, ids=lambda item: str(item))
def test_each_projection_reads_the_kept_record_of_its_major(kind: str, major: int) -> None:
    """A projection is code that knows a format, so its era's real record is what proves it."""
    kept = [name for name in KEPT_NAMES if format_of(name).kind == kind and major_of(name) == major]

    assert kept, f"no kept record of {kind} major {major}"
    for name in kept:
        compared = read_comparable(RECORDS / name, format_of(name))
        assert compared.projected is not None


def test_each_installed_view_derives_only_what_it_names_on_its_kept_record() -> None:
    """`check_view` walks every value, so it runs here on real records and never on a read.

    No installed contract declares a view yet; the first one is held to this the day it lands.
    """
    for (kind, major), view in installed_views().items():
        kept = [
            name for name in KEPT_NAMES if format_of(name).kind == kind and major_of(name) == major
        ]
        assert kept, f"a view of {kind} major {major} has no kept record to prove it on"
        for name in kept:
            record = json.loads((RECORDS / name).read_text(encoding="ascii"))
            assert check_view(view, record) == [], name

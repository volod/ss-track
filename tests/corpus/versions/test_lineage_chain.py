"""A successor resting on a missing, rebuilt, damaged or malformed predecessor is not built."""

from pathlib import Path

import pytest
import yaml

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus
from tests.corpus.conftest import (
    HEAD,
    WriteCorpus,
    corpus_declaration,
    encounter_of,
    group_of,
    single_group,
    stream_of,
)
from tests.corpus.versions._lineage_build import build_version, refused_build


def test_a_missing_predecessor_is_not_built_and_reads_no_source(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    (first.manifest_path.parent / "source.mkv").unlink()
    groups = [single_group("site-a", "development", stream_of(first))]

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        groups,
        RefusalCode.CORPUS_NOT_BUILT,
        supersedes="pilot-v1",
    )

    assert refusal.details == {"corpus_id": "pilot-v1"}


def test_a_missing_older_version_of_the_chain_is_not_built(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    v1 = build_version(write_grouped_corpus, data_root, "pilot-v1", groups)
    build_version(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")
    v1.manifest_path.unlink()

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v3",
        groups,
        RefusalCode.CORPUS_NOT_BUILT,
        supersedes="pilot-v2",
    )

    assert refusal.details == {"corpus_id": "pilot-v1"}


def test_a_rebuilt_predecessor_is_refused_when_its_successor_is_named(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    v1 = build_version(write_grouped_corpus, data_root, "pilot-v1", groups)
    build_version(write_grouped_corpus, data_root, "pilot-v2", groups, supersedes="pilot-v1")
    v1.manifest_path.chmod(0o644)
    v1.manifest_path.unlink()
    window = stream_of(first, selection=HEAD)
    build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", window)]
    )

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v3",
        groups,
        RefusalCode.CORPUS_CONFLICT,
        supersedes="pilot-v2",
    )

    assert refusal.details["pinned_manifest_sha256"] == v1.manifest_sha256


def test_a_damaged_predecessor_is_refused(
    first: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    groups = [single_group("site-a", "development", stream_of(first))]
    v1 = build_version(write_grouped_corpus, data_root, "pilot-v1", groups)
    v1.manifest_path.chmod(0o644)
    v1.manifest_path.write_text("{}", encoding="ascii")

    refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        groups,
        RefusalCode.RECORD_TAMPERED,
        supersedes="pilot-v1",
    )


@pytest.mark.parametrize(
    ("value", "words"),
    [
        pytest.param("pilot-v1", "supersede itself", id="itself"),
        pytest.param("Not A Name", "/supersedes", id="not-an-identifier"),
        pytest.param(None, "/supersedes", id="null"),
        pytest.param(7, "/supersedes", id="number"),
    ],
)
def test_a_malformed_supersedes_is_refused(
    media: Path, data_root: Path, value: object, words: str
) -> None:
    declared = media / "corpus.yaml"
    stream = {"stream_id": "one", "source_sha256": "a" * 64}
    group = group_of("site-a", "development", encounter_of("enc", stream))
    body = corpus_declaration([group], supersedes=value)
    declared.write_text(yaml.safe_dump(body), encoding="utf-8")

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(declared, data_root)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert words in caught.value.message

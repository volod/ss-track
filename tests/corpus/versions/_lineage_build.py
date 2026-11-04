"""Building linked corpus versions in one call, for the lineage tests."""

from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, ImportResult, RefusalCode, build_corpus
from ss_track.corpus.versions.builder import BuildResult
from tests.corpus.conftest import Group, WriteCorpus


def build_version(
    write: WriteCorpus, data_root: Path, version: str, groups: list[Group], **fields: object
) -> BuildResult:
    return build_corpus(write(groups, corpus_id=version, **fields), data_root)


def refused_build(
    write: WriteCorpus,
    data_root: Path,
    version: str,
    groups: list[Group],
    code: RefusalCode,
    **fields: object,
) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        build_version(write, data_root, version, groups, **fields)
    assert caught.value.code is code
    assert not (data_root / "corpus" / version).exists()
    return caught.value


def source_of(imported: ImportResult) -> dict[str, str]:
    return {"source_sha256": imported.source_sha256}

"""A one-stream encounter group and a refused build, for the grouping tests."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode, build_corpus
from tests.corpus.conftest import Group, WriteCorpus, encounter_of, group_of


def refused_grouping(
    write: WriteCorpus,
    groups: Sequence[Group],
    data_root: Path,
    code: RefusalCode,
    **overrides: object,
) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write(list(groups), **overrides), data_root)
    assert caught.value.code is code
    assert not (data_root / "corpus").exists()
    return caught.value


def encounter_group(group_id: str, split: str, encounter: str, stream: dict[str, object]) -> Group:
    return group_of(group_id, split, encounter_of(encounter, stream))

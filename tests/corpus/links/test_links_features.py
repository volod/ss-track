"""A link review compares the feature rows of a discovery run bound to the same staged version."""

from pathlib import Path
from typing import Any

import pytest

from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.discovery.run import run_discovery
from ss_track.corpus.links.run import LinkRequest, write_links
from ss_track.corpus.records.kinds import CORPUS_LINKS
from tests.corpus.conftest import WriteCorpus, encounter_of, group_of, stream_of
from tests.corpus.discovery._plan import RUN_ID, plan_document, worker_environ, write_plan
from tests.corpus.discovery.conftest import caches, sibling_python
from tests.corpus.siblings._fake_sibling import Caches

__all__ = ["caches", "sibling_python"]


def _staged(corpus_id: str, results: list[ImportResult], write: WriteCorpus, root: Path) -> None:
    groups = [
        group_of(
            f"group-{index}",
            "development",
            encounter_of(f"enc-{index}", stream_of(result, stream_id=f"s{index}")),
        )
        for index, result in enumerate(results)
    ]
    build_corpus(write(groups, corpus_id=corpus_id), root)
    stage_corpus(corpus_id, root)


@pytest.fixture
def discovered(
    first: ImportResult,
    second: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    media: Path,
    caches: Caches,
    sibling_python: Path,
) -> Path:
    """A staged version and a discovery run over it, with one tiled and one whole extractor."""
    _staged("pilot-v1", [first, second], write_grouped_corpus, data_root)
    document = plan_document(caches)
    del document["hints"]
    tiled: dict[str, Any] = dict(document["embedding"]["extractors"][0])
    tiled |= {"extractor_id": "clip-tiles", "tiles": {"columns": 2, "rows": 1}}
    document["embedding"]["extractors"].append(tiled)
    run_discovery(
        write_plan(media, document), data_root, environ=worker_environ(caches, sibling_python)
    )
    return data_root


def test_each_plan_extractor_is_one_background_method_over_its_tile_positions(
    discovered: Path,
) -> None:
    result = write_links(LinkRequest("links-1", "pilot-v1", features_run_id=RUN_ID), discovered)

    record: Any = read_sealed(result.path, CORPUS_LINKS)
    assert record["features"]["run_id"] == RUN_ID
    backgrounds = [method for method in record["methods"] if method["method"] != "luma-grid-16"]
    assert [(m["extractor_id"], m["run_extractor_ids"]) for m in backgrounds] == [
        ("clip-b16", ["clip-b16"]),
        ("clip-tiles", ["clip-tiles.r0c0", "clip-tiles.r0c1"]),
    ]
    assert record["not_compared"] == []


def test_a_discovery_run_of_another_version_is_refused(
    discovered: Path,
    third: ImportResult,
    write_grouped_corpus: WriteCorpus,
) -> None:
    _staged("pilot-v2", [third], write_grouped_corpus, discovered)

    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("links-1", "pilot-v2", features_run_id=RUN_ID), discovered)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "pilot-v1" in caught.value.message


def test_a_missing_discovery_run_is_refused(discovered: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        write_links(LinkRequest("links-1", "pilot-v1", features_run_id="absent"), discovered)

    assert caught.value.code is RefusalCode.RECORD_TAMPERED

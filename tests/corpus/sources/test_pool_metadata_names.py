"""An operator name rule joins a provider CSV whose names omit the video directory."""

from pathlib import Path

import pytest

from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import CORPUS_POOL
from ss_track.corpus.sources.pool import prepare_pool
from tests.corpus.sources._pool_fixture import _declared, _video, publish, write_pool

VIDEO = "videos/no_drone_footage/birds_only/rgb/1.mp4"
CSV = "metadata/videos_no_drone.csv"


def _acquired(data_root: Path) -> None:
    publish(
        data_root,
        "acq-drone",
        "huggingface",
        "owner/dataset",
        "d" * 40,
        {VIDEO: b"bird-bytes"},
        [_video(VIDEO)],
        {CSV: b"name,license\n\nno_drone/birds_only/rgb/1,cc-1.0\n"},
    )


def _pool(tmp_path: Path, name: str, rules: list[dict[str, str]] | None) -> Path:
    collection = _declared("acq-drone", {VIDEO: "development"})
    if rules is not None:
        collection["metadata_names"] = rules
    return write_pool(tmp_path / f"{name}.yaml", name, [collection])


def test_the_rule_records_the_csv_license_on_its_video(tmp_path: Path, data_root: Path) -> None:
    _acquired(data_root)
    without = prepare_pool(_pool(tmp_path, "pool-plain", None), "pool-plain", data_root)
    rule = {"file": CSV, "name_prefix": "no_drone/", "path_prefix": "videos/no_drone_footage/"}
    joined = prepare_pool(_pool(tmp_path, "pool-named", [rule]), "pool-named", data_root)

    plain = read_sealed(without.path, CORPUS_POOL)["videos"]
    named = read_sealed(joined.path, CORPUS_POOL)["videos"]
    assert isinstance(plain, list) and isinstance(named, list)
    assert isinstance(plain[0], dict) and isinstance(named[0], dict)
    assert (plain[0]["association"], plain[0]["license"]) == ("missing", None)
    assert (named[0]["association"], named[0]["license"]) == ("matched", "cc-1.0")
    assert named[0]["license_reference"] == CSV


@pytest.mark.parametrize(
    "rule",
    [
        {"file": "metadata/absent.csv", "name_prefix": "", "path_prefix": "videos/"},
        {"file": CSV, "name_prefix": "", "path_prefix": "videos/../"},
        {"file": CSV, "name_prefix": "no_drone", "path_prefix": "videos/"},
    ],
)
def test_an_unusable_rule_is_refused(tmp_path: Path, data_root: Path, rule: dict[str, str]) -> None:
    _acquired(data_root)
    with pytest.raises(CorpusRefusal) as caught:
        prepare_pool(_pool(tmp_path, "pool-bad", [rule]), "pool-bad", data_root)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_repeated_rule_is_refused(tmp_path: Path, data_root: Path) -> None:
    _acquired(data_root)
    rule = {"file": CSV, "name_prefix": "", "path_prefix": "videos/"}
    with pytest.raises(CorpusRefusal) as caught:
        prepare_pool(_pool(tmp_path, "pool-twice", [rule, rule]), "pool-twice", data_root)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID

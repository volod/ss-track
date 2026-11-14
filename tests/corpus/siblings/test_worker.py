"""The embedding worker returns rows keyed by frame reference, and refuses what it cannot pin.

Each test runs the real worker script under the fake sibling environment, over really staged
bundles, and asks the fake for one defect the sibling study found in the pinned release.
"""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import ImportResult, build_corpus, stage_corpus
from ss_track.corpus.bundles.bundle_reader import open_corpus_bundle
from ss_track.corpus.bundles.frames import FrameBundle
from ss_track.corpus.discovery.plan import ExtractorPlan
from ss_track.corpus.siblings.embedding import ExtractorRows, embed_streams
from ss_track.corpus.siblings.worker_env import PYTHON_VARIABLE, worker_environment, worker_python
from ss_track.corpus.storage.layout import frames_root
from ss_track.corpus.versions.manifests import load_corpus_manifest
from tests.corpus.conftest import WriteCorpus, stream_of
from tests.corpus.siblings._fake_sibling import (
    COMMIT,
    DIMENSIONS,
    Caches,
    clip_extractor,
    create_environment,
    dino_extractor,
    embedding_plan,
)

CORPUS = "pilot-v1"


@pytest.fixture
def bundles(
    first: ImportResult, second: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> list[FrameBundle]:
    streams = [stream_of(first, stream_id="one"), stream_of(second, stream_id="two")]
    build_corpus(write_corpus(streams), data_root)
    stage_corpus(CORPUS, data_root)
    corpus = load_corpus_manifest(CORPUS, data_root)
    root = frames_root(data_root, CORPUS)
    return [open_corpus_bundle(name, corpus, root) for name in ("one", "two")]


def _embed(
    python: Path,
    caches: Caches,
    bundles: list[FrameBundle],
    extractor: ExtractorPlan,
    frame_stride: int = 1,
    timeout: float = 60.0,
) -> ExtractorRows:
    plan = embedding_plan([extractor], frame_stride)
    (rows,) = embed_streams(
        plan, extractor, bundles, python=python, timeout=timeout, environ=caches.environ
    )
    return rows


def _refused(
    code: RefusalCode,
    python: Path,
    caches: Caches,
    bundles: list[FrameBundle],
    extractor: ExtractorPlan,
    timeout: float = 60.0,
) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        _embed(python, caches, bundles, extractor, timeout=timeout)
    assert caught.value.code is code, caught.value.to_record()
    return caught.value


def test_rows_map_exactly_to_the_frame_references_sent(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    extractor = clip_extractor(caches)

    rows = _embed(sibling_python, caches, bundles, extractor, frame_stride=5)

    for bundle, stream in zip(bundles, rows.streams, strict=True):
        refs = [ref for ref in bundle.frame_refs() if ref.frame_index % 5 == 0]
        assert stream.stream_id == bundle.stream_id
        assert stream.bundle_sha256 == bundle.bundle_sha256
        assert stream.keys == tuple((ref.frame_index, ref.sha256) for ref in refs)
        vectors = np.frombuffer(stream.vectors, dtype="<f4").reshape(len(refs), DIMENSIONS)
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-6)
    assert rows.provenance["weights"] == [caches.clip_weight()]
    assert rows.provenance["package"] == {
        "name": "ss-perception",
        "version": "0.2.1",
        "commit": COMMIT,
    }
    assert rows.provenance["preprocessing"] == {
        "resize": "short_side",
        "crop": "center",
        "interpolation": "bicubic",
        "input_width": 224,
        "input_height": 224,
        "mean": [0.48145466, 0.4578275, 0.40821073],
        "std": [0.26862954, 0.26130258, 0.27577711],
    }
    assert (rows.provenance["device"], rows.provenance["batch_size"]) == ("cpu", 4)


def test_retries_return_the_same_rows(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    extractor = dino_extractor(caches)

    assert _embed(sibling_python, caches, bundles, extractor) == _embed(
        sibling_python, caches, bundles, extractor
    )


def test_progress_on_standard_output_never_reaches_the_protocol(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    extractor = clip_extractor(caches)
    expected = _embed(sibling_python, caches, bundles, extractor)
    caches.defects(stdout=True)

    assert _embed(sibling_python, caches, bundles, extractor) == expected


@pytest.mark.parametrize(
    ("defect", "code", "message"),
    [
        ("env", RefusalCode.EXTRACTOR_UNPINNED, "changed the environment"),
        ("dotenv_checkpoint", RefusalCode.EXTRACTOR_UNPINNED, "changed the environment"),
        ("download", RefusalCode.EXTRACTOR_UNPINNED, "network access is refused"),
        ("no_cuda", RefusalCode.EXTRACTOR_INCOMPATIBLE, "not on the requested device"),
        ("oom", RefusalCode.EXTRACTOR_INCOMPATIBLE, "changed device"),
        ("short", RefusalCode.WORKER_FAILED, "another shape"),
        ("unnormalized", RefusalCode.WORKER_FAILED, "not unit length"),
        ("crash", RefusalCode.WORKER_FAILED, "ended before its answer"),
    ],
)
def test_each_sibling_defect_is_refused_never_recorded(
    sibling_python: Path,
    caches: Caches,
    bundles: list[FrameBundle],
    defect: str,
    code: RefusalCode,
    message: str,
) -> None:
    caches.defects(**{defect: True})
    device = "cuda" if defect in {"no_cuda", "oom"} else "cpu"

    refusal = _refused(
        code, sibling_python, caches, bundles, clip_extractor(caches, device=device, batch_size=2)
    )

    assert message in refusal.message


def test_a_sibling_cannot_read_ancestor_dotenv(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    """A sibling environment inside a project can discover that project's .env."""
    caches.defects(ancestor_dotenv=True)
    (caches.home / "hf" / ".env").write_text("SST_TEST_UNTRUSTED=1\n", encoding="ascii")
    refusal = _refused(
        RefusalCode.EXTRACTOR_UNPINNED, sibling_python, caches, bundles, clip_extractor(caches)
    )
    assert "environment file" in refusal.message
    assert "SST_TEST_UNTRUSTED" not in str(refusal.to_record())


def test_a_set_checkpoint_is_refused_before_any_worker_starts(
    caches: Caches, bundles: list[FrameBundle]
) -> None:
    environ = caches.environ | {"DINO_CHECKPOINT": "/models/dino_ssl_3.pt"}
    extractor = dino_extractor(caches)

    with pytest.raises(CorpusRefusal) as caught:
        embed_streams(
            embedding_plan([extractor]),
            extractor,
            bundles,
            python=Path("/no/python"),
            environ=environ,
        )

    assert caught.value.code is RefusalCode.EXTRACTOR_UNPINNED


def test_an_active_checkpoint_file_is_refused(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle], tmp_path: Path
) -> None:
    extractor = dino_extractor(caches)
    plan = embedding_plan([extractor])
    original = worker_environment

    def with_active(
        extractor: ExtractorPlan, neutral: Path, environ: object = None
    ) -> dict[str, str]:
        found = original(extractor, neutral, caches.environ)
        (tmp_path / "ckpt").mkdir(exist_ok=True)
        (tmp_path / "ckpt" / "active_checkpoint.txt").write_text("/models/dino_ssl.pt")
        return found | {"SUP_CHECKPOINT_DIR": str(tmp_path / "ckpt")}

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("ss_track.corpus.siblings.embedding.worker_environment", with_active)
        with pytest.raises(CorpusRefusal) as caught:
            embed_streams(plan, extractor, bundles, python=sibling_python, environ=caches.environ)

    assert caught.value.code is RefusalCode.EXTRACTOR_UNPINNED
    assert "adapted DINO checkpoint" in caught.value.message


def test_weights_other_than_the_pinned_ones_are_refused(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    pinned = caches.clip_weight() | {"sha256": "0" * 64}

    refusal = _refused(
        RefusalCode.EXTRACTOR_UNPINNED,
        sibling_python,
        caches,
        bundles,
        clip_extractor(caches, weights=(pinned,)),
    )

    assert refusal.details["found"] == [caches.clip_weight()]


def test_a_weight_with_no_immutable_revision_is_refused(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    caches.defects(loose_weights=True)

    refusal = _refused(
        RefusalCode.EXTRACTOR_UNPINNED, sibling_python, caches, bundles, dino_extractor(caches)
    )

    assert "no immutable revision" in refusal.message


@pytest.mark.parametrize(
    ("changes", "defects", "what"),
    [
        ({"dimensions": 16}, {}, "row length"),
        ({}, {"alias": "dinov2_vitb14_reg"}, "architecture"),
    ],
)
def test_an_incompatible_model_is_refused(
    sibling_python: Path,
    caches: Caches,
    bundles: list[FrameBundle],
    changes: dict[str, object],
    defects: dict[str, object],
    what: str,
) -> None:
    caches.defects(**defects)
    extractor = dino_extractor(caches, **changes)

    refusal = _refused(
        RefusalCode.EXTRACTOR_INCOMPATIBLE, sibling_python, caches, bundles, extractor
    )

    assert refusal.message == f"the worker's {what} does not match the plan"


def test_a_package_without_a_commit_is_refused(
    tmp_path: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    python = create_environment(tmp_path / "no-commit", commit=None)

    refusal = _refused(
        RefusalCode.EXTRACTOR_UNPINNED, python, caches, bundles, clip_extractor(caches)
    )

    assert "records no commit" in refusal.message


def test_a_slow_worker_is_stopped_at_its_deadline(
    sibling_python: Path, caches: Caches, bundles: list[FrameBundle]
) -> None:
    caches.defects(hang=True)

    refusal = _refused(
        RefusalCode.WORKER_FAILED,
        sibling_python,
        caches,
        bundles,
        clip_extractor(caches),
        timeout=2.0,
    )

    assert "did not answer within 2 s" in refusal.message


def test_the_worker_interpreter_is_named_by_the_operator(tmp_path: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        worker_python({})
    assert caught.value.code is RefusalCode.WORKER_FAILED
    assert worker_python({PYTHON_VARIABLE: str(tmp_path / "python")}) == tmp_path / "python"


def test_a_missing_interpreter_is_a_worker_failure(
    caches: Caches, bundles: list[FrameBundle]
) -> None:
    refusal = _refused(
        RefusalCode.WORKER_FAILED, Path("/no/such/python"), caches, bundles, clip_extractor(caches)
    )

    assert "cannot start" in refusal.message


def test_the_worker_environment_is_explicit_and_offline(tmp_path: Path) -> None:
    environ = {"PATH": "/bin", "DATA_DIR": "/data", "SECRET_TOKEN": "x", "DINO_CHECKPOINT": "/c"}
    extractor = ExtractorPlan("dino", "d", "dinov3_vitb14", None, "cpu", 4, 768, ())

    found = worker_environment(extractor, tmp_path, environ)

    assert "SECRET_TOKEN" not in found
    assert found["DATA_DIR"] == str(tmp_path) and found["DINO_CHECKPOINT"] == ""
    assert found["HF_HUB_OFFLINE"] == "1" and found["USE_FP16"] == "false"
    assert json.dumps(found)  # nothing but strings


@pytest.mark.parametrize(
    ("lie", "message"),
    [
        ("garbage", "something other than the protocol"),
        ("unknown_code", "no"),
        ("incomplete", "account of what it loaded is incomplete"),
        ("keys", "rows for other frames"),
        ("partial", "partial batch"),
        ("nonunit", "not finite unit vectors"),
        ("short_payload", "ended before its answer was complete"),
    ],
)
def test_a_worker_that_breaks_the_protocol_is_refused(
    sibling_python: Path,
    caches: Caches,
    bundles: list[FrameBundle],
    monkeypatch: pytest.MonkeyPatch,
    lie: str,
    message: str,
) -> None:
    weights = [caches.clip_weight()]
    (Path(caches.environ["HF_HOME"]) / "lie.json").write_text(
        json.dumps({"lie": lie, "weights": weights})
    )
    monkeypatch.setattr(
        "ss_track.corpus.siblings.worker_process.WORKER_SCRIPT",
        Path(__file__).with_name("_lying_worker.py"),
    )
    original = worker_environment

    def with_commit(
        extractor: ExtractorPlan, neutral: Path, environ: object = None
    ) -> dict[str, str]:
        return original(extractor, neutral, caches.environ) | {"LIE_COMMIT": COMMIT}

    monkeypatch.setattr("ss_track.corpus.siblings.embedding.worker_environment", with_commit)

    refusal = _refused(
        RefusalCode.WORKER_FAILED, sibling_python, caches, bundles, clip_extractor(caches)
    )

    assert message in refusal.message


def test_a_later_unpinned_extractor_is_refused_before_any_frame_is_embedded(
    sibling_python: Path,
    caches: Caches,
    bundles: list[FrameBundle],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extractors embed one after another, so every pin is checked before the first embeds."""
    from types import SimpleNamespace

    from ss_track.corpus.discovery import run as discovery_run

    stale = dino_extractor(caches)
    stale = replace(stale, weights=({**stale.weights[0], "revision": "tree-sha256:" + "0" * 64},))
    plan = SimpleNamespace(embedding=embedding_plan([clip_extractor(caches), stale]))

    def embedded(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("an extractor embedded frames before every pin was checked")

    monkeypatch.setattr(discovery_run, "embed_streams", embedded)
    environ = caches.environ | {PYTHON_VARIABLE: str(sibling_python)}
    with pytest.raises(CorpusRefusal) as caught:
        discovery_run._features(plan, bundles, environ, 60.0)  # type: ignore[arg-type]
    assert caught.value.code is RefusalCode.EXTRACTOR_UNPINNED

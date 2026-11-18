"""Two independently prepared data roots and the handoff calls the portable-review tests share."""

from datetime import date, timedelta
from pathlib import Path

import yaml

from ss_track.corpus import build_corpus, import_source, stage_corpus
from ss_track.corpus.links.portable import export_handoff
from ss_track.corpus.storage.layout import discovery_run_directory
from tests.corpus._media import WIDTH, write_clip
from tests.corpus.conftest import corpus_declaration, encounter_of, group_of, recording_declaration

CORPUS = "portable-v1"
LINKS = "portable-links"
REVIEWER = "Reviewer"


def write_inputs(root: Path) -> tuple[list[Path], Path]:
    root.mkdir()
    declarations = []
    for name, extra in (("one.mkv", 2), ("two.mkv", 4)):
        write_clip(root / name, width=WIDTH + extra)
        declaration = root / f"{name}.yaml"
        declaration.write_text(yaml.safe_dump(recording_declaration(name)), encoding="ascii")
        declarations.append(declaration)
    return declarations, root / "corpus.yaml"


def prepare(data_root: Path, declarations: list[Path], corpus_path: Path) -> tuple[str, str]:
    first, second = [import_source(path, data_root) for path in declarations]
    groups = [
        group_of(
            "first-group",
            "development",
            encounter_of(
                "first-encounter",
                {"stream_id": "first", "source_sha256": first.source_sha256},
            ),
        ),
        group_of(
            "second-group",
            "development",
            encounter_of(
                "second-encounter",
                {"stream_id": "second", "source_sha256": second.source_sha256},
            ),
        ),
    ]
    corpus_path.write_text(
        yaml.safe_dump(corpus_declaration(groups, corpus_id=CORPUS)), encoding="ascii"
    )
    build_corpus(corpus_path, data_root)
    stage_corpus(CORPUS, data_root)
    return first.source_sha256, second.source_sha256


def expiry(days: int = 7) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def checkpoint_of(data_root: Path) -> Path:
    return discovery_run_directory(data_root, LINKS) / "link-review" / "decisions.yaml"


def export(data_root: Path, archive: Path, recipes: list[Path], identity: str) -> None:
    export_handoff(
        data_root,
        LINKS,
        CORPUS,
        identity,
        expiry(),
        archive,
        recipes,
        REVIEWER,
    )

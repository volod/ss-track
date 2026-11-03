"""An end-to-end run demonstrates the suite-wide output gate covers every writer."""

import json
from collections import Counter
from pathlib import Path

from ss_track.cli import EXIT_OK, main
from ss_track.corpus import build_corpus, compare_staged_hashes, record_staged_hashes, stage_corpus
from ss_track.corpus.importer import ImportResult
from ss_track.schema import validate_file
from tests.corpus.conftest import WriteCorpus, stream_of
from tests.corpus.test_generated_cases import every_case


def test_all_writer_formats_and_transform_branches_are_checked(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    validate_written_contracts: Counter[str],
) -> None:
    before = validate_written_contracts.copy()
    declaration = write_corpus([stream_of(imported, generated_cases=every_case())])
    assert validate_file(declaration, contract_name="declaration/corpus")
    built = build_corpus(declaration, data_root)
    stage_corpus(built.corpus_id, data_root)
    hashes = record_staged_hashes(built.corpus_id, "contracts", data_root)
    compared = compare_staged_hashes(hashes.record_path, hashes.record_path, "contracts", data_root)
    assert main(["contracts", "validate", "--file", str(compared.record_path)]) == EXIT_OK
    counts = validate_written_contracts - before
    assert set(counts) == {
        "record/corpus-manifest",
        "record/frame-bundle",
        "record/frame-set",
        "record/staged-hashes",
        "record/hash-comparison",
        "result/command",
    }
    assert counts["record/frame-bundle"] == 1 + len(every_case())
    for path in (data_root / "corpus" / built.corpus_id).rglob("*.json"):
        assert validate_file(path).seal_checked
    assert json.loads(compared.record_path.read_text())["status"] == "identical"

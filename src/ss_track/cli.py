"""Command-line entrypoint for project diagnostics and corpus provenance."""

import argparse
import json
import logging
from collections.abc import Callable, Sequence
from pathlib import Path

from ss_track.corpus import (
    AmendmentResult,
    BuildResult,
    ComparisonResult,
    CorpusRefusal,
    FramesResult,
    ImportResult,
    RefusalCode,
    StagedHashesResult,
    amend_source_terms,
    compare_staged_hashes,
    record_staged_hashes,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus import build_corpus as run_corpus_build
from ss_track.corpus import import_source as run_import
from ss_track.metadata import project_info
from ss_track.paths import resolve_data_root
from ss_track.schema import ContractList, ValidationResult, list_contracts, validate_file
from ss_track.schema.docs import DocsResult, render_docs
from ss_track.schema.freeze import EvolutionResult, diff_contract, freeze_contract

EXIT_OK = 0
EXIT_REFUSED = 1

_LOG = logging.getLogger(__name__)


def _log_json(level: int, record: dict[str, object]) -> None:
    _LOG.log(level, "%s", json.dumps(record, sort_keys=True))


def _refuse(refusal: CorpusRefusal) -> int:
    _log_json(logging.ERROR, dict(refusal.to_record()))
    return EXIT_REFUSED


type CorpusResult = (
    ImportResult
    | AmendmentResult
    | BuildResult
    | FramesResult
    | StagedHashesResult
    | ComparisonResult
)


def _report(action: Callable[[Path], CorpusResult]) -> int:
    """Run one action on the data root and report its one JSON record."""
    return _reported(lambda: action(resolve_data_root()))


def _reported(
    action: Callable[
        [], CorpusResult | ContractList | ValidationResult | EvolutionResult | DocsResult
    ],
) -> int:
    """Run one action and report one JSON record for its result or its refusal."""
    try:
        result = action()
    except CorpusRefusal as refusal:
        return _refuse(refusal)
    except OSError as error:
        return _refuse(CorpusRefusal(RefusalCode.STORAGE_FAILED, f"storage failed: {error}"))
    _log_json(logging.INFO, dict(result.to_record()))
    return EXIT_OK


def _run_info(_: argparse.Namespace) -> int:
    info = project_info()
    _LOG.info("%s %s (%s)", info.distribution, info.version, info.package)
    return EXIT_OK


def _run_import(args: argparse.Namespace) -> int:
    action = amend_source_terms if args.amend_terms else run_import
    return _report(lambda data_root: action(args.source, data_root))


def _run_corpus_build(args: argparse.Namespace) -> int:
    return _report(lambda data_root: run_corpus_build(args.manifest, data_root))


def _run_corpus_stage(args: argparse.Namespace) -> int:
    return _report(lambda data_root: stage_corpus(args.corpus, data_root))


def _run_corpus_verify(args: argparse.Namespace) -> int:
    return _report(lambda data_root: verify_corpus_frames(args.corpus, data_root))


def _run_corpus_hashes(args: argparse.Namespace) -> int:
    return _report(lambda data_root: record_staged_hashes(args.corpus, args.run_id, data_root))


def _run_corpus_compare(args: argparse.Namespace) -> int:
    return _report(
        lambda data_root: compare_staged_hashes(args.left, args.right, args.run_id, data_root)
    )


def _run_contracts_list(_: argparse.Namespace) -> int:
    return _reported(list_contracts)


def _run_contracts_validate(args: argparse.Namespace) -> int:
    return _reported(
        lambda: validate_file(args.file, contract_name=args.contract, version=args.version)
    )


def _run_contracts_diff(args: argparse.Namespace) -> int:
    return _reported(lambda: diff_contract(args.contract, args.file, args.root))


def _run_contracts_freeze(args: argparse.Namespace) -> int:
    return _reported(
        lambda: freeze_contract(
            args.contract,
            args.file,
            root=args.root,
            summary=args.summary,
            migration=args.migration,
            disposition=args.disposition,
            owner=args.owner,
        )
    )


def _add_evolution_commands(
    commands: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    for name, handler in (("diff", _run_contracts_diff), ("freeze", _run_contracts_freeze)):
        command = commands.add_parser(name, help=f"{name} a candidate contract")
        command.add_argument("contract", help="family/id")
        command.add_argument("--file", type=Path, required=True, help="candidate schema JSON")
        command.add_argument(
            "--root", type=Path, help="writable contract set; defaults to installed set"
        )
        command.set_defaults(handler=handler)
        if name == "freeze":
            command.add_argument("--summary", required=True)
            command.add_argument("--migration")
            command.add_argument("--disposition", choices=("view", "facts", "retired"))
            command.add_argument("--owner", help="owning capability for an initial contract")


def _add_contract_commands(
    subcommands: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> None:
    """Add the commands that read only the contract set, so they need no data root."""
    contracts = subcommands.add_parser("contracts", help="read the published data contracts")
    commands = contracts.add_subparsers(dest="contracts_command", required=True)
    docs = commands.add_parser("docs", help="write contract reference Markdown")
    docs.add_argument("--out", type=Path, required=True)
    docs.set_defaults(handler=lambda args: _reported(lambda: render_docs(args.out)))
    listing = commands.add_parser("list", help="list every contract and its frozen versions")
    listing.set_defaults(handler=_run_contracts_list)
    validate = commands.add_parser("validate", help="check one file under a frozen contract")
    validate.add_argument(
        "--file",
        type=Path,
        required=True,
        help="JSON record/result, or YAML with --contract declaration/<id>",
    )
    validate.add_argument(
        "--contract", help="<family>/<id>; taken from the file's kind when omitted"
    )
    validate.add_argument(
        "--version", help="an exact frozen version; the newest of the file's major when omitted"
    )
    validate.set_defaults(handler=_run_contracts_validate)
    _add_evolution_commands(commands)


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser independently for tests and future subcommands."""
    parser = argparse.ArgumentParser(prog="ss-track")
    subcommands = parser.add_subparsers(dest="command", required=True)

    info = subcommands.add_parser("info", help="show the installed project identity")
    info.set_defaults(handler=_run_info)

    source = subcommands.add_parser("import", help="import one declared recording")
    source.add_argument("--source", type=Path, required=True, help="recording declaration (YAML)")
    source.add_argument(
        "--amend-terms",
        action="store_true",
        help="record new rights and sensitivity for an imported source",
    )
    source.set_defaults(handler=_run_import)

    corpus = subcommands.add_parser("corpus", help="manage corpus versions")
    corpus_commands = corpus.add_subparsers(dest="corpus_command", required=True)
    build = corpus_commands.add_parser("build", help="build one corpus version")
    build.add_argument("--manifest", type=Path, required=True, help="corpus declaration (YAML)")
    build.set_defaults(handler=_run_corpus_build)
    stage = corpus_commands.add_parser("stage", help="stage decoded frames for a corpus version")
    stage.add_argument("--corpus", required=True, help="built corpus_id")
    stage.set_defaults(handler=_run_corpus_stage)
    verify = corpus_commands.add_parser(
        "verify", help="verify every staged frame and the source records it rests on"
    )
    verify.add_argument("--corpus", required=True, help="built corpus_id")
    verify.set_defaults(handler=_run_corpus_verify)
    hashes = corpus_commands.add_parser(
        "hashes", help="record a verified corpus's hashes and this host, for comparison"
    )
    hashes.add_argument("--corpus", required=True, help="staged corpus_id")
    hashes.add_argument("--run-id", required=True, help="run that keeps the record")
    hashes.set_defaults(handler=_run_corpus_hashes)
    compare = corpus_commands.add_parser(
        "compare", help="compare the staged hashes that two hosts recorded"
    )
    compare.add_argument("--left", type=Path, required=True, help="one staged-hashes.json")
    compare.add_argument("--right", type=Path, required=True, help="the other staged-hashes.json")
    compare.add_argument("--run-id", required=True, help="run that keeps the comparison")
    compare.set_defaults(handler=_run_corpus_compare)
    _add_contract_commands(subcommands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected command and return a process status."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args(argv)
    status: int = args.handler(args)
    return status


if __name__ == "__main__":
    raise SystemExit(main())

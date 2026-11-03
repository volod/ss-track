"""A static scan: no production code reads a sealed record around the one read path."""

import ast
from collections.abc import Iterator
from dataclasses import fields
from pathlib import Path

import pytest

import ss_track
from ss_track.schema import ValidationResult, commands

_PACKAGE = Path(ss_track.__file__).parent
_GATE = Path("corpus/sealed.py")
_FACTS_READER = Path("corpus/amendment.py")  # reads a `facts` record to write its successor
_DECLARATION_LOADER = Path("schema/enforce.py")  # validates a declaration; serializes records
_CONTRACT_FILE_READER = Path("schema/store.py")  # reads the contract set, which holds no record
_DEEP_CHECK = Path("schema/commands.py")  # gives a verdict on a file, and hands no record onward
_DEEP_PARSER = Path("schema/_documents.py")  # private parser of the deep check and declarations
# The loader parses only the JSON it serialized itself, to validate a record as it will be written.
_JSON_READERS = {_GATE, _CONTRACT_FILE_READER, _DEEP_PARSER, _DECLARATION_LOADER}
_YAML_READERS = {_CONTRACT_FILE_READER, _DEEP_PARSER}
_PARSER_USERS = {_DEEP_CHECK, _DECLARATION_LOADER}
_LOADERS = {"json.load", "json.loads", "yaml.load", "yaml.safe_load"}
_READS = {"read_sealed", "read_stated", "read_comparable"}


def _called_name(call: ast.Call) -> str:
    target = call.func
    if isinstance(target, ast.Attribute):
        owner = target.value.id if isinstance(target.value, ast.Name) else "?"
        return f"{owner}.{target.attr}"
    return target.id if isinstance(target, ast.Name) else ""


def _imported_names(tree: ast.AST) -> Iterator[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                yield f"{node.module}.{alias.name}"


def _call_findings(call: ast.Call, relative: Path) -> Iterator[str]:
    called = _called_name(call)
    is_yaml_load = called.startswith("yaml.") and "load" in called
    if called in {"json.load", "json.loads"} and relative not in _JSON_READERS:
        yield f"calls {called}"
    if is_yaml_load and relative not in _YAML_READERS:
        yield f"calls {called}"
    if called == "read_stated" and relative != _FACTS_READER:
        yield "reads stated facts outside the amendment"
    if called in _READS and (len(call.args) != 2 or call.keywords):
        yield f"calls {called} without exactly a path and a format"


def _names_version(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "schema_version"
    ) or (
        isinstance(node, ast.Call)
        and _called_name(node).endswith(".get")
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "schema_version"
    )


def _compare_findings(compare: ast.Compare, relative: Path) -> Iterator[str]:
    """A record's major decides only on the read path, which states each route in one place."""
    if relative != _GATE and any(map(_names_version, [compare.left, *compare.comparators])):
        yield "checks a record's major outside the read path"


def scan(source: str, relative: Path) -> list[str]:
    """Name each way this module could reach a record without passing the gate."""
    tree = ast.parse(source)
    found = [f"imports {name}" for name in _imported_names(tree) if name in _LOADERS]
    if relative not in _PARSER_USERS:
        found.extend(
            f"imports private deep parser {name}"
            for name in _imported_names(tree)
            if name.startswith("ss_track.schema._documents.")
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "require_schema":
            found.append("names require_schema")
        elif isinstance(node, ast.Call):
            found.extend(_call_findings(node, relative))
        elif isinstance(node, ast.Compare):
            found.extend(_compare_findings(node, relative))
    return found


def _modules() -> list[Path]:
    return sorted(path.relative_to(_PACKAGE) for path in _PACKAGE.rglob("*.py"))


@pytest.mark.parametrize("module", _modules(), ids=str)
def test_no_module_reads_a_sealed_record_around_the_gate(module: Path) -> None:
    assert scan((_PACKAGE / module).read_text(encoding="utf-8"), module) == []


def test_every_read_of_a_record_file_goes_through_the_gate() -> None:
    readers = [
        module
        for module in _modules()
        if module.parts[0] == "corpus"
        and ".read_text(" in (_PACKAGE / module).read_text(encoding="utf-8")
    ]

    assert readers == [_GATE]


def test_the_deep_check_returns_a_verdict_and_never_the_record() -> None:
    returned = {field.name for field in fields(ValidationResult)}

    assert returned == {"path", "contract", "version", "urn", "seal_checked"}
    assert not hasattr(commands, "read_document")


def test_the_facts_route_is_still_used() -> None:
    source = (_PACKAGE / _FACTS_READER).read_text(encoding="utf-8")

    assert "read_stated(" in source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("import json\njson.loads(text)", "calls json.loads", id="json-loads"),
        pytest.param("import json\njson.load(handle)", "calls json.load", id="json-load"),
        pytest.param("from json import loads", "imports json.loads", id="json-import"),
        pytest.param("import yaml\nyaml.safe_load(text)", "calls yaml.safe_load", id="yaml"),
        pytest.param("require_schema(record, 1, path)", "names require_schema", id="old-pair"),
        pytest.param(
            "read_sealed(path)",
            "calls read_sealed without exactly a path and a format",
            id="no-format",
        ),
        pytest.param(
            "read_sealed(path, FORMAT, older_majors=(1,))",
            "calls read_sealed without exactly a path and a format",
            id="older",
        ),
        pytest.param(
            "read_stated(path, FORMAT)", "reads stated facts outside the amendment", id="stated"
        ),
        pytest.param(
            'if record["schema_version"] == 1: pass',
            "checks a record's major outside the read path",
            id="version",
        ),
        pytest.param(
            'if 2 > record.get("schema_version"): pass',
            "checks a record's major outside the read path",
            id="get",
        ),
    ],
)
def test_the_scan_finds_each_way_around_the_gate(source: str, expected: str) -> None:
    assert expected in scan(source, Path("corpus/elsewhere.py"))

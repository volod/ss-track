"""A static scan: no production code reads a sealed record around the one read path."""

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

import ss_track

_PACKAGE = Path(ss_track.__file__).parent
_GATE = Path("corpus/sealed.py")
_OLDER_MAJOR_READER = Path("corpus/amendment.py")
_DECLARATION_LOADER = Path("corpus/fields.py")
_LOADERS = {"json.load", "json.loads", "yaml.load", "yaml.safe_load"}


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
    if called in {"json.load", "json.loads"} and relative != _GATE:
        yield f"calls {called}"
    if is_yaml_load and relative != _DECLARATION_LOADER:
        yield f"calls {called}"
    names_older = any(keyword.arg == "older_majors" for keyword in call.keywords)
    if names_older and relative != _OLDER_MAJOR_READER:
        yield "reads an older major"
    if called == "read_sealed" and len(call.args) != 2:
        yield "calls read_sealed without a format"


def scan(source: str, relative: Path) -> list[str]:
    """Name each way this module could reach a record without passing the gate."""
    tree = ast.parse(source)
    found = [f"imports {name}" for name in _imported_names(tree) if name in _LOADERS]
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "require_schema":
            found.append("names require_schema")
        elif isinstance(node, ast.Call):
            found.extend(_call_findings(node, relative))
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

    assert sorted(readers) == sorted([_GATE, _DECLARATION_LOADER])


def test_the_exemption_for_an_older_major_is_still_used() -> None:
    source = (_PACKAGE / _OLDER_MAJOR_READER).read_text(encoding="utf-8")

    assert "older_majors=" in source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param("import json\njson.loads(text)", "calls json.loads", id="json-loads"),
        pytest.param("import json\njson.load(handle)", "calls json.load", id="json-load"),
        pytest.param("from json import loads", "imports json.loads", id="json-import"),
        pytest.param("import yaml\nyaml.safe_load(text)", "calls yaml.safe_load", id="yaml"),
        pytest.param("require_schema(record, 1, path)", "names require_schema", id="old-pair"),
        pytest.param("read_sealed(path)", "calls read_sealed without a format", id="no-format"),
        pytest.param(
            "read_sealed(path, FORMAT, older_majors=(1,))", "reads an older major", id="older"
        ),
    ],
)
def test_the_scan_finds_each_way_around_the_gate(source: str, expected: str) -> None:
    assert expected in scan(source, Path("corpus/elsewhere.py"))

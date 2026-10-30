from pathlib import Path

from agent_py.quality.doc_links import (
    anchors,
    broken_links,
    documentation_files,
    heading_anchor,
    main,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, name: str, text: str) -> Path:
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_repository_documentation_links_resolve() -> None:
    assert broken_links(PROJECT_ROOT) == []


def test_heading_slugs_drop_punctuation_and_number_duplicates(tmp_path: Path) -> None:
    document = _write(tmp_path, "docs/topic.md", "# API + CLI\n\n## Result\n\n## Result\n")

    assert heading_anchor("API + CLI") == "api--cli"
    assert anchors(document) == {"api--cli", "result", "result-1"}


def test_missing_file_and_anchor_are_both_reported(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "README.md",
        "# Root\n\n[missing](docs/gone.md)\n[stale](docs/topic.md#old)\n",
    )
    _write(tmp_path, "docs/topic.md", "# Current heading\n")

    assert broken_links(tmp_path) == [
        "README.md:3: missing file -> docs/gone.md",
        "README.md:4: missing anchor -> docs/topic.md#old",
    ]


def test_external_and_fenced_links_are_ignored(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "README.md",
        "# Root\n\n[web](https://example.com)\n\n```text\n[x](gone.md)\n```\n",
    )

    assert broken_links(tmp_path) == []


def test_cursor_rule_is_part_of_documentation_sources(tmp_path: Path) -> None:
    cursor_rule = _write(tmp_path, ".cursor/rules/project.mdc", "# Rule\n")

    assert documentation_files(tmp_path) == [cursor_rule]


def test_main_returns_failure_for_a_broken_link(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", "# Root\n\n[x](missing.md)\n")

    assert main(["--root", str(tmp_path)]) == 1

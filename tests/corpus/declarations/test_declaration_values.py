"""Values YAML reads its own way, such as dates and `1.0`, and a declaration of another major."""

from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.declarations.declaration import (
    load_corpus_declaration,
    load_recording_declaration,
)
from tests.corpus.declarations._declarations import CORPUS, RECORDING, refused_recording, writer_in


@pytest.fixture
def declare(tmp_path: Path) -> Callable[[str], Path]:
    return writer_in(tmp_path)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        pytest.param("retain_until: null", "retain_until: 2030-06-15", id="canonical"),
        pytest.param("retain_until: null", "retain_until: '2030-06-15'", id="quoted"),
    ],
)
def test_an_unquoted_date_is_its_iso_text_where_a_date_belongs(
    declare: Callable[[str], Path], old: str, new: str
) -> None:
    declaration = load_recording_declaration(declare(RECORDING.replace(old, new)))

    assert declaration.rights.retain_until == "2030-06-15"
    assert type(declaration.rights.retain_until) is str


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        pytest.param("holder: Owner", "holder: 2024-01-05", "YAML date", id="date-as-text"),
        pytest.param(
            "retain_until: null", "retain_until: 2030-02-30", "cannot read", id="impossible-date"
        ),
        pytest.param(
            "retain_until: null", "retain_until: 2030-6-5", "retain_until", id="short-form"
        ),
        pytest.param(
            "retain_until: null",
            "retain_until: 2030-06-15 10:00:00",
            "cannot read",
            id="timestamp",
        ),
    ],
)
def test_an_unquoted_date_is_refused_unless_it_is_one_iso_day(
    declare: Callable[[str], Path], old: str, new: str, message: str
) -> None:
    assert message in refused_recording(declare(RECORDING.replace(old, new)))


def test_an_unquoted_date_is_not_a_corpus_name(declare: Callable[[str], Path]) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_declaration(
            declare(CORPUS.replace("corpus_id: pilot-v1", "corpus_id: 2024-01-05"))
        )

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert caught.value.message.startswith("declaration.yaml breaks ")
    assert "/corpus_id '2024-01-05' is a YAML date where text belongs" in caught.value.message


def test_an_unquoted_date_is_not_capture_text(declare: Callable[[str], Path]) -> None:
    """A capture fact takes text or a number, and an unquoted date is text only to YAML 1.2."""
    message = refused_recording(declare(RECORDING + "capture: {lens: 2024-01-05}\n"))

    assert "/capture/lens" in message
    assert "YAML date where text belongs" in message


def test_a_quoted_date_is_capture_text(declare: Callable[[str], Path]) -> None:
    declaration = load_recording_declaration(declare(RECORDING + "capture: {lens: '2024-01-05'}\n"))

    assert declaration.capture["lens"] == "2024-01-05"


@pytest.mark.parametrize("index", ["1.0", "1e0", "true"])
def test_an_index_must_be_a_true_integer(declare: Callable[[str], Path], index: str) -> None:
    text = CORPUS.replace(
        "stream_id: one,", f"selection: {{start_frame: {index}, end_frame: 5}}, stream_id: one,"
    )
    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_declaration(declare(text))

    assert caught.value.code is RefusalCode.MANIFEST_INVALID


def test_a_declaration_of_another_major_names_its_stamp_first(
    declare: Callable[[str], Path],
) -> None:
    text = RECORDING.replace("schema_version: 3", "schema_version: 1").replace(
        "derived_frames: true", "derived_frames: true, extra: 1"
    )

    message = refused_recording(declare(text))

    assert message.endswith("/schema_version 3 was expected")

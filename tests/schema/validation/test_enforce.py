"""Runtime enforcement: the installed contracts, as readers and writers reach them."""

from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.schema.validation.enforce import is_shared_type, older_remedy, read_declaration


def test_a_reader_of_a_major_with_no_frozen_contract_is_a_damaged_set(tmp_path: Path) -> None:
    path = tmp_path / "recording.yaml"
    path.write_text("schema_version: 9\n", encoding="utf-8")

    with pytest.raises(CorpusRefusal) as caught:
        read_declaration(path, "declaration/recording", 9)

    assert caught.value.code is RefusalCode.CONTRACT_SET_INVALID


def test_an_unreadable_declaration_is_a_manifest_refusal(tmp_path: Path) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        read_declaration(tmp_path / "absent.yaml", "declaration/recording", 2)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "cannot read absent.yaml" in caught.value.message


@pytest.mark.parametrize(
    ("type_name", "value", "expected"),
    [
        pytest.param("identifier", "pilot-v1", True, id="identifier"),
        pytest.param("identifier", "../escape", False, id="traversal"),
        pytest.param("identifier", "pilot\n", False, id="final-newline"),
        pytest.param("sha256", "a" * 64, True, id="digest"),
        pytest.param("sha256", "A" * 64, False, id="uppercase-digest"),
    ],
)
def test_a_shared_type_is_checked_as_every_contract_states_it(
    type_name: str, value: str, expected: bool
) -> None:
    assert is_shared_type(type_name, value) is expected


def test_a_kind_no_contract_states_has_no_migration() -> None:
    assert older_remedy("ss-track.unknown", 1) is None
    assert older_remedy("ss-track.frame-set", 0) is None
    assert older_remedy("ss-track.source-manifest", 1) == (
        "Record its terms with ss-track import --amend-terms."
    )

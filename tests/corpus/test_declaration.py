from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.corpus.declaration import load_corpus_declaration, load_recording_declaration
from ss_track.refusal import CorpusRefusal, RefusalCode

SHA256 = "a" * 64
RECORDING = """\
schema_version: 2
source: {path: clip.mkv}
rights: {holder: Owner, basis: owned, retention: one year, sharing: restricted, retain_until: null, derived_frames: true}
sensitivity: {level: low}
"""
CORPUS = f"""\
schema_version: 3
corpus_id: pilot-v1
scenario_rights: {{sharing: restricted, max_sensitivity: moderate}}
groups:
  - group_id: site-a
    split: development
    encounters:
      - encounter_id: enc01
        streams:
          - {{stream_id: one, source_sha256: "{SHA256}"}}
"""


@pytest.fixture
def declare(tmp_path: Path) -> Callable[[str], Path]:
    def write(text: str) -> Path:
        path = tmp_path / "declaration.yaml"
        path.write_text(text, encoding="utf-8")
        return path

    return write


def _refused_recording(path: Path) -> str:
    with pytest.raises(CorpusRefusal) as caught:
        load_recording_declaration(path)
    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    return caught.value.message


def test_minimal_recording_keeps_unknown_capture_facts_explicit(
    declare: Callable[[str], Path], tmp_path: Path
) -> None:
    declaration = load_recording_declaration(declare(RECORDING))

    assert declaration.source_path == tmp_path / "clip.mkv"
    assert declaration.expected_sha256 is None
    assert declaration.capture_clock_evidence is None
    assert declaration.capture["camera"] is None
    assert declaration.capture["range"] == {"status": "unknown", "value_m": None, "method": None}


def test_full_recording_is_read(declare: Callable[[str], Path]) -> None:
    text = RECORDING.replace("{path: clip.mkv}", f"{{path: clip.mkv, sha256: {SHA256}}}") + (
        "timestamps: {capture_clock_evidence: hardware clock}\n"
        "capture:\n"
        "  camera: bench camera\n"
        "  fov: 62.2\n"
        "  range: {status: measured, value_m: 12.5, method: laser rangefinder}\n"
    )

    declaration = load_recording_declaration(declare(text))

    assert declaration.expected_sha256 == SHA256
    assert declaration.capture_clock_evidence == "hardware clock"
    assert declaration.capture["fov"] == 62.2
    assert declaration.capture["range"] == {
        "status": "measured",
        "value_m": 12.5,
        "method": "laser rangefinder",
    }


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        pytest.param(
            "rights: {holder: Owner, basis: owned, retention: one year, sharing: restricted, retain_until: null, derived_frames: true}\n",
            "",
            "rights",
            id="no-rights",
        ),
        pytest.param("sensitivity: {level: low}\n", "", "sensitivity", id="no-sensitivity"),
        pytest.param("basis: owned", "basis: unknown", "basis", id="rights-cannot-be-unknown"),
        pytest.param("holder: Owner", "holder: '  '", "holder", id="blank-holder"),
        pytest.param("sharing: restricted", "sharing: maybe", "sharing", id="bad-sharing"),
        pytest.param("level: low", "level: 3", "level", id="number-as-text"),
        pytest.param("schema_version: 2", "schema_version: 1", "schema_version", id="old-schema"),
        pytest.param(
            "schema_version: 2", "schema_version: true", "schema_version", id="bool-schema"
        ),
        pytest.param(
            "schema_version: 2", "schema_version: 2.0", "schema_version", id="float-schema"
        ),
        pytest.param(
            "{path: clip.mkv}", "{path: clip.mkv, sha256: abc}", "sha256", id="short-hash"
        ),
        pytest.param(
            "{path: clip.mkv}",
            "{path: clip.mkv, sha256: " + "A" * 64 + "}",
            "sha256",
            id="upper-hash",
        ),
        pytest.param(
            "{path: clip.mkv}",
            "{path: clip.mkv, rights: x}",
            "Additional properties",
            id="unknown-nested",
        ),
        pytest.param("source: {path: clip.mkv}", "source: clip.mkv", "/source", id="scalar-source"),
    ],
)
def test_malformed_recordings_are_refused(
    declare: Callable[[str], Path], old: str, new: str, message: str
) -> None:
    assert old in RECORDING
    assert message in _refused_recording(declare(RECORDING.replace(old, new)))


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        pytest.param("rightz: {}\n", "Additional properties", id="misspelled-section"),
        pytest.param("capture: {camra: x}\n", "Additional properties", id="misspelled-capture"),
        pytest.param("capture: {fov: .nan}\n", "finite", id="nan"),
        pytest.param("capture: {fov: .inf}\n", "finite", id="infinity"),
        pytest.param("capture: {fov: true}\n", "/capture/fov", id="boolean"),
        pytest.param("capture: {lens: [a, b]}\n", "/capture/lens", id="list"),
        pytest.param("capture: {range: {status: measured}}\n", "requires", id="range-no-method"),
        pytest.param("capture: {range: {value_m: 3}}\n", "unknown", id="range-value-unknown"),
        pytest.param("capture: {range: {status: guessed}}\n", "status", id="range-bad-status"),
        pytest.param(
            "timestamps: {capture_clock_evidence: ''}\n", "non-empty", id="blank-evidence"
        ),
        pytest.param("sensitivity: {level: low}\n", "duplicate key", id="duplicate-key"),
        pytest.param("? [a, b]\n: value\n", "unhashable", id="unhashable-key"),
        pytest.param("rights: [unclosed\n", "cannot read", id="syntax-error"),
    ],
)
def test_bad_additions_are_refused(
    declare: Callable[[str], Path], extra: str, message: str
) -> None:
    assert message in _refused_recording(declare(RECORDING + extra))


def test_missing_and_non_utf8_declarations_are_refused(
    declare: Callable[[str], Path], tmp_path: Path
) -> None:
    assert "cannot read" in _refused_recording(tmp_path / "absent.yaml")
    binary = declare("")
    binary.write_bytes(b"\xff\xfe\x00")
    assert "cannot read" in _refused_recording(binary)
    assert "is not of type 'object'" in _refused_recording(declare(""))


def test_minimal_corpus(declare: Callable[[str], Path]) -> None:
    declaration = load_corpus_declaration(declare(CORPUS))

    assert declaration.corpus_id == "pilot-v1"
    assert declaration.decode_policy_sha256 is None
    assert declaration.scenario_rights.sharing == "restricted"
    assert declaration.scenario_rights.max_sensitivity == "moderate"
    [(group, encounter, stream)] = list(declaration.members())
    assert (group.group_id, group.split) == ("site-a", "development")
    assert encounter.encounter_id == "enc01"
    assert (stream.stream_id, stream.source_sha256) == ("one", SHA256)
    assert stream.selection is None


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        pytest.param("corpus_id: pilot-v1", "corpus_id: ../escape", "corpus_id", id="traversal"),
        pytest.param("corpus_id: pilot-v1", "corpus_id: UPPER", "corpus_id", id="uppercase"),
        pytest.param("stream_id: one", "stream_id: a/b", "stream_id", id="stream-slash"),
        pytest.param("group_id: site-a", "group_id: ../up", "group_id", id="group-traversal"),
        pytest.param("encounter_id: enc01", "encounter_id: E1", "encounter_id", id="encounter"),
        pytest.param("split: development", "split: test", "split", id="unknown-split"),
        pytest.param("split: development", "split: no", "split", id="yaml-boolean-split"),
        pytest.param("schema_version: 3", "schema_version: 2", "schema_version", id="old-schema"),
        pytest.param("sharing: restricted", "sharing: open", "sharing", id="unknown-sharing"),
        pytest.param(
            "scenario_rights: {sharing: restricted, max_sensitivity: moderate}\n",
            "",
            "scenario_rights",
            id="no-scenario-rights",
        ),
        pytest.param(
            ", max_sensitivity: moderate", "", "max_sensitivity", id="no-sensitivity-limit"
        ),
        pytest.param("    split: development\n", "", "split", id="no-split"),
        pytest.param("groups:", "sequences:", "sequences", id="old-sequences-key"),
        pytest.param(
            "    encounters:\n      - encounter_id: enc01\n        streams:\n"
            f'          - {{stream_id: one, source_sha256: "{SHA256}"}}\n',
            "    encounters: []\n",
            "non-empty",
            id="no-encounters",
        ),
        pytest.param(
            f'        streams:\n          - {{stream_id: one, source_sha256: "{SHA256}"}}\n',
            "        streams: []\n",
            "non-empty",
            id="no-streams",
        ),
        pytest.param(SHA256, "../../etc", "source_sha256", id="hash-traversal"),
        pytest.param(
            "stream_id: one,",
            "selection: {start_frame: 5, end_frame: 5}, stream_id: one,",
            "start_frame",
            id="empty-window",
        ),
        pytest.param(
            "stream_id: one,",
            "selection: {start_frame: -1, end_frame: 5}, stream_id: one,",
            "/start_frame",
            id="negative",
        ),
        pytest.param(
            "stream_id: one,",
            "selection: {start_frame: true, end_frame: 5}, stream_id: one,",
            "/start_frame",
            id="bool-index",
        ),
        pytest.param(
            CORPUS[CORPUS.index("groups:") :],
            "groups: []\n",
            "non-empty",
            id="no-groups",
        ),
    ],
)
def test_malformed_corpora_are_refused(
    declare: Callable[[str], Path], old: str, new: str, message: str
) -> None:
    assert old in CORPUS
    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_declaration(declare(CORPUS.replace(old, new)))

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert message in caught.value.message


@pytest.mark.parametrize(
    ("old", "new"),
    [
        pytest.param("retain_until: null", "retain_until: 2030-06-15", id="canonical"),
        pytest.param("retain_until: null", "retain_until: '2030-06-15'", id="quoted"),
    ],
)
def test_an_unquoted_date_keeps_today_s_result_where_a_date_belongs(
    declare: Callable[[str], Path], old: str, new: str
) -> None:
    declaration = load_recording_declaration(declare(RECORDING.replace(old, new)))

    assert declaration.rights.retain_until == "2030-06-15"
    assert type(declaration.rights.retain_until) is str


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        pytest.param("holder: Owner", "holder: 2024-01-05", "not a date", id="date-as-text"),
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
def test_an_unquoted_date_keeps_today_s_refusal_elsewhere(
    declare: Callable[[str], Path], old: str, new: str, message: str
) -> None:
    assert message in _refused_recording(declare(RECORDING.replace(old, new)))


def test_an_unquoted_date_is_not_a_corpus_name(declare: Callable[[str], Path]) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_declaration(
            declare(CORPUS.replace("corpus_id: pilot-v1", "corpus_id: 2024-01-05"))
        )

    assert caught.value.code is RefusalCode.MANIFEST_INVALID
    assert "not a date" in caught.value.message


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
    text = RECORDING.replace("schema_version: 2", "schema_version: 1").replace(
        "derived_frames: true", "derived_frames: true, extra: 1"
    )

    message = _refused_recording(declare(text))

    assert message.endswith("/schema_version 2 was expected")

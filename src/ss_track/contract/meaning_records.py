"""Semantic checks for analytics, samples and G1 trial records."""

from collections.abc import Callable, Iterable

from google.protobuf.message import Message

from ss_track.contract.checks import (
    check_date,
    child,
    enum_name,
    flag,
    number_field,
    reject,
    require_non_negative,
    require_sha256,
    require_text,
    same_clock_order,
    text_field,
)

Checker = Callable[[Message], None]

_MANIFEST = (
    "run_id",
    "corpus_id",
    "split",
    "scenario_pack_id",
    "metric_suite",
    "module_id",
    "schema_revision",
    "host_id",
    "compute_variant",
)
_OPTIONAL_SHA = (
    "annotation_sha256",
    "mask_sha256",
    "class_map_sha256",
    "module_config_sha256",
)
_SENSOR = frozenset({"SAMPLE_VALID", "SAMPLE_MISSING", "SAMPLE_STALE", "SAMPLE_INVALID"})
_RESOURCE = frozenset({"SAMPLE_VALID", "SAMPLE_INVALID", "SAMPLE_MULTIPLEXED"})


def record_checkers() -> dict[str, Checker]:
    """Return the checkers for the analytics and trial packages."""
    return {
        "RunManifest": check_manifest,
        "ValidationResult": check_validation,
        "SensorSample": check_sensor,
        "ResourceSample": check_resource,
        "PowerSample": check_power,
        "DerivedEnergy": check_energy,
        "InstrumentRecord": check_instrument,
        "CalibrationRecord": check_calibration,
        "HardwareTrial": check_trial,
    }


def check_manifest(message: Message) -> None:
    """A run manifest names the inputs it used and the interval it covers."""
    for name in _MANIFEST:
        require_text(text_field(message, name), name)
    for name in _OPTIONAL_SHA:
        digest = text_field(message, name)
        if digest:
            require_sha256(digest, name)
    urns = _texts(message, "contract_urns")
    if not urns:
        reject("contract_urns is missing")
    for urn in urns:
        if not urn.startswith("urn:ss-track:contract:"):
            reject("contract_urns must be contract URNs")
    if not message.HasField("interval_start") or not message.HasField("interval_end"):
        reject("a run manifest needs an interval")


def check_validation(message: Message) -> None:
    """A non-valid result says why. A valid result may omit the reason."""
    if not message.HasField("ref"):
        reject("validation result needs an event ref")
    status = enum_name(message, "status")
    if status == "SCORE_STATUS_UNSPECIFIED":
        reject("validation status is missing")
    if status != "VALID":
        require_text(text_field(message, "reason"), "reason")


def check_sensor(message: Message) -> None:
    """A sensor sample names its modality, unit and validity. It is not an observation."""
    _sample(message, "sensor sample", _SENSOR, "valid, missing, stale or invalid")


def check_resource(message: Message) -> None:
    """A resource sample names its counter scope, unit, source and validity."""
    require_text(text_field(message, "scope"), "scope")
    require_text(text_field(message, "source"), "source")
    _sample(message, "resource sample", _RESOURCE, "valid, invalid or multiplexed")


def check_power(message: Message) -> None:
    """Watts use W. Voltage and current use V*A. Joules are a derived event."""
    if not message.HasField("ref"):
        reject("power sample needs an event ref")
    require_text(text_field(message, "instrument_id"), "instrument_id")
    require_text(text_field(message, "boundary"), "boundary")
    require_text(text_field(message, "calibration_id"), "calibration_id")
    _uncertainty(message, "power uncertainty")
    for item in _texts(message, "quality_flags"):
        require_text(item, "quality flag")
    reading = message.WhichOneof("reading")
    unit = text_field(message, "unit")
    if reading == "watts" and unit == "W":
        return
    if reading == "electrical" and unit == "V*A":
        return
    if reading == "watts":
        reject("watts are measured in W")
    if reading == "electrical":
        reject("voltage and current are measured in V*A")
    reject("power sample needs watts or voltage and current")


def check_energy(message: Message) -> None:
    """Derived joules name their method and the exact interval they integrate."""
    if not message.HasField("ref"):
        reject("derived energy needs an event ref")
    if not flag(child(message, "ref"), "unframed"):
        reject("derived energy is an unframed interval")
    require_text(text_field(message, "method"), "method")
    if text_field(message, "unit") != "J":
        reject("derived energy is measured in J")
    require_non_negative(number_field(message, "joules"), "joules")
    _uncertainty(message, "energy uncertainty")
    if not message.HasField("start") or not message.HasField("end"):
        reject("derived energy needs a start and an end")
    same_clock_order(child(message, "start"), child(message, "end"))


def check_instrument(message: Message) -> None:
    """An instrument is identified by its id. It is not a frame event."""
    require_text(text_field(message, "instrument_id"), "instrument_id")
    require_text(text_field(message, "measurand"), "measurand")
    require_text(text_field(message, "unit"), "unit")
    require_text(text_field(message, "model"), "model")
    _optional_non_negative(message, "resolution")
    _optional_non_negative(message, "bandwidth_hz")
    _optional_non_negative(message, "uncertainty")


def check_calibration(message: Message) -> None:
    """A calibration names its instrument, method, date and uncertainty."""
    require_text(text_field(message, "calibration_id"), "calibration_id")
    require_text(text_field(message, "instrument_id"), "instrument_id")
    require_text(text_field(message, "method"), "method")
    check_date(text_field(message, "checked_on"))
    _optional_non_negative(message, "uncertainty")


def check_trial(message: Message) -> None:
    """A trial names its protocol, host, traces and validity."""
    require_text(text_field(message, "trial_id"), "trial_id")
    require_text(text_field(message, "protocol_id"), "protocol_id")
    require_text(text_field(message, "host_id"), "host_id")
    for digest in _texts(message, "trace_sha256"):
        require_sha256(digest, "trace_sha256")
    if not message.HasField("start") or not message.HasField("end"):
        reject("a hardware trial needs a start and an end")
    _optional_non_negative(message, "uncertainty")
    validity = enum_name(message, "validity")
    if validity == "TRIAL_VALIDITY_UNSPECIFIED":
        reject("trial validity is missing")
    if validity != "VALID":
        require_text(text_field(message, "reason"), "reason")


def _sample(message: Message, label: str, allowed: frozenset[str], description: str) -> None:
    if not message.HasField("ref") or not message.HasField("time"):
        reject(f"{label} needs a ref and a time")
    require_text(text_field(message, "unit"), "unit")
    if message.DESCRIPTOR.name == "SensorSample":
        require_text(text_field(message, "modality"), "modality")
    validity = enum_name(message, "validity")
    if validity not in allowed:
        reject(f"{label} validity must be {description}")


def _uncertainty(message: Message, label: str) -> None:
    if not message.HasField("uncertainty"):
        reject(f"{label} is missing")
    require_non_negative(number_field(message, "uncertainty"), label)


def _optional_non_negative(message: Message, name: str) -> None:
    if message.HasField(name):
        require_non_negative(number_field(message, name), name)


def _texts(message: Message, name: str) -> list[str]:
    value = getattr(message, name)
    if isinstance(value, str) or not isinstance(value, Iterable):
        reject(f"{name} must be a list")
    texts = []
    for item in value:
        if not isinstance(item, str):
            reject(f"{name} must be text")
        texts.append(item)
    return texts

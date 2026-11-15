"""The frozen eligibility mask. It repeats each label disposition and holds no score."""

from dataclasses import dataclass

from ss_track.annotate.disposition import Disposition, DispositionStatus
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.label_rules import label_dispositions
from ss_track.annotate.result import AnnotationEntry
from ss_track.corpus.declarations.fields import Fields, invalid

type FrameKey = tuple[str, int]


@dataclass(frozen=True, slots=True)
class MaskFrame:
    """The frozen status of one labeled frame."""

    instance_id: str
    frame_index: int
    disposition: str
    reason: str | None


@dataclass(frozen=True, slots=True)
class Episode:
    """Eligibility of one instance over a half-open frame window."""

    episode_id: str
    instance_id: str
    start_frame: int
    end_frame: int
    eligibility: str
    exclusion_reason: str | None


@dataclass(frozen=True, slots=True)
class MaskSet:
    """One mask document and the hash a later freeze pins."""

    mask_id: str
    label_sha256: str
    frames: tuple[MaskFrame, ...]
    episodes: tuple[Episode, ...]
    document_sha256: str


def read_mask(fields: Fields, document_sha256: str) -> MaskSet:
    """Return the typed mask. Agreement with the labels is applied by the caller."""
    return MaskSet(
        mask_id=fields.string("mask_id"),
        label_sha256=fields.string("label_sha256"),
        frames=tuple(_frame(Fields(item, fields.where)) for item in fields.items("frames")),
        episodes=tuple(_episode(Fields(item, fields.where)) for item in fields.items("episodes")),
        document_sha256=document_sha256,
    )


def check_mask(mask: MaskSet, labels: LabelSet) -> None:
    """Refuse a mask that disagrees with the labels or freezes an unverifiable frame as scorable."""
    if mask.label_sha256 != labels.document_sha256:
        raise invalid("label_sha256 does not match the label document")
    expected = label_dispositions(labels)
    found = _require_frames(mask, expected)
    _require_episodes(mask, labels, expected, found)


def mask_entries(mask: MaskSet) -> tuple[AnnotationEntry, ...]:
    """Return one row per mask frame. The row carries the frozen status and no score."""
    return tuple(
        AnnotationEntry(row.instance_id, row.frame_index, _status(row.disposition), row.reason)
        for row in mask.frames
    )


def _require_frames(
    mask: MaskSet, expected: dict[FrameKey, Disposition]
) -> dict[FrameKey, MaskFrame]:
    found: dict[FrameKey, MaskFrame] = {}
    for row in mask.frames:
        key = (row.instance_id, row.frame_index)
        if key in found:
            raise invalid(f"duplicate mask frame {row.instance_id} {row.frame_index}")
        wanted = expected.get(key)
        if wanted is None:
            raise invalid(f"mask has no label for {row.instance_id} frame {row.frame_index}")
        if (row.disposition, row.reason) != (wanted.status, wanted.reason):
            raise invalid(
                f"mask {row.instance_id} frame {row.frame_index} is {row.disposition}"
                f" but the label is {wanted.status}"
            )
        found[key] = row
    if set(found) != set(expected):
        instance, frame = sorted(set(expected) - set(found))[0]
        raise invalid(f"mask omits {instance} frame {frame}")
    return found


def _require_episodes(
    mask: MaskSet,
    labels: LabelSet,
    expected: dict[FrameKey, Disposition],
    found: dict[FrameKey, MaskFrame],
) -> None:
    instances = {item.instance_id for item in labels.instances}
    covered: dict[FrameKey, str] = {}
    for episode in mask.episodes:
        _require_window(episode, labels.space.frame_count, instances)
        keys = [
            key
            for key in expected
            if key[0] == episode.instance_id and episode.start_frame <= key[1] < episode.end_frame
        ]
        if not keys:
            raise invalid(f"episode {episode.episode_id} covers no labeled frame")
        for key in keys:
            if key in covered:
                raise invalid(f"{key[0]} frame {key[1]} is in more than one episode")
            covered[key] = episode.episode_id
        _require_eligibility(episode, keys, expected)
    if set(covered) != set(found):
        instance, frame = sorted(set(found) - set(covered))[0]
        raise invalid(f"{instance} frame {frame} is outside every episode")


def _require_window(episode: Episode, frame_count: int, instances: set[str]) -> None:
    if episode.instance_id not in instances:
        raise invalid(f"episode {episode.episode_id} names unknown instance {episode.instance_id}")
    if episode.start_frame >= episode.end_frame:
        raise invalid(f"episode {episode.episode_id} has an empty window")
    if episode.end_frame > frame_count:
        raise invalid(f"episode {episode.episode_id} ends outside the source")


def _require_eligibility(
    episode: Episode, keys: list[FrameKey], expected: dict[FrameKey, Disposition]
) -> None:
    scorable = [key for key in keys if expected[key].status == "scorable"]
    if episode.eligibility == "eligible" and not scorable:
        raise invalid(f"episode {episode.episode_id} is eligible and has no scorable frame")
    if episode.eligibility == "eligible" and episode.exclusion_reason is not None:
        raise invalid(f"episode {episode.episode_id} is eligible and states an exclusion reason")
    if episode.eligibility == "excluded" and episode.exclusion_reason is None:
        raise invalid(f"episode {episode.episode_id} is excluded without a reason")


def _status(value: str) -> DispositionStatus:
    if value == "scorable":
        return "scorable"
    if value == "unscorable":
        return "unscorable"
    if value == "not_denominator":
        return "not_denominator"
    raise TypeError(f"disposition {value} is not in the contract")


def _frame(fields: Fields) -> MaskFrame:
    return MaskFrame(
        fields.string("instance_id"),
        fields.index("frame_index"),
        fields.string("disposition"),
        fields.nullable_text("reason"),
    )


def _episode(fields: Fields) -> Episode:
    return Episode(
        fields.string("episode_id"),
        fields.string("instance_id"),
        fields.index("start_frame"),
        fields.index("end_frame"),
        fields.string("eligibility"),
        fields.nullable_text("exclusion_reason"),
    )

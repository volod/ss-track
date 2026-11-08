"""Upstream collection membership on a recording declaration and its source record.

A membership is copied from the declaration. Nothing in it is inferred from a license code, a
folder name, or a missing metadata field.
"""

from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import Fields


class OriginMembership:
    """One collection whose bytes are this recording."""

    def __init__(
        self,
        provider: str,
        collection_id: str,
        provider_version: str,
        video_path: str,
        content_sha256: str,
        upstream_split: str | None,
        source_reference: str | None,
        annotation_reference: str | None,
        attribution: str,
        terms: str,
        terms_reference: str,
        license_name: str | None,
        license_reference: str | None,
        metadata_sha256: str | None,
    ) -> None:
        self.provider = provider
        self.collection_id = collection_id
        self.provider_version = provider_version
        self.video_path = video_path
        self.content_sha256 = content_sha256
        self.upstream_split = upstream_split
        self.source_reference = source_reference
        self.annotation_reference = annotation_reference
        self.attribution = attribution
        self.terms = terms
        self.terms_reference = terms_reference
        self.license_name = license_name
        self.license_reference = license_reference
        self.metadata_sha256 = metadata_sha256

    def to_record(self) -> dict[str, JsonValue]:
        """Return the contract object, including explicit nulls."""
        return {
            "provider": self.provider,
            "collection_id": self.collection_id,
            "provider_version": self.provider_version,
            "video_path": self.video_path,
            "content_sha256": self.content_sha256,
            "upstream_split": self.upstream_split,
            "source_reference": self.source_reference,
            "annotation_reference": self.annotation_reference,
            "attribution": self.attribution,
            "terms": self.terms,
            "terms_reference": self.terms_reference,
            "license": self.license_name,
            "license_reference": self.license_reference,
            "metadata_sha256": self.metadata_sha256,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OriginMembership):
            return NotImplemented
        return self.to_record() == other.to_record()


def read_origins(fields: Fields) -> tuple[OriginMembership, ...]:
    """Return recorded memberships, or none when the declaration omits origin."""
    if not fields.has("origin"):
        return ()
    return tuple(
        _membership(Fields(item, f"{fields.where}.origin[{index}]"))
        for index, item in enumerate(fields.items("origin"))
    )


def _membership(fields: Fields) -> OriginMembership:
    return OriginMembership(
        fields.text("provider"),
        fields.text("collection_id"),
        fields.text("provider_version"),
        fields.text("video_path"),
        fields.text("content_sha256"),
        fields.nullable_text("upstream_split"),
        fields.nullable_text("source_reference"),
        fields.nullable_text("annotation_reference"),
        fields.text("attribution"),
        fields.text("terms"),
        fields.text("terms_reference"),
        fields.nullable_text("license"),
        fields.nullable_text("license_reference"),
        fields.nullable_text("metadata_sha256"),
    )

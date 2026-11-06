"""Corpus versions: the build, reading a built version, encounter grouping and splits, and lineage
across versions.

`scan` walks every version on one data root for the listings that refuse nothing: `unlinked`
names other versions that place a source elsewhere, `impact` names versions that pin a replaced
source record, and `near_duplicates` reports a likely re-encode across groups, including one in a
version the declaration does not link.
"""

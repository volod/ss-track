"""Build the deterministic Croissant document for exported record tables."""

import hashlib
from collections.abc import Mapping
from typing import Any

CONTEXT: dict[str, Any] = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "cr": "http://mlcommons.org/croissant/",
    "sc": "https://schema.org/",
    "dct": "http://purl.org/dc/terms/",
    "conformsTo": "dct:conformsTo",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileObject": "cr:fileObject",
    "recordSet": "cr:recordSet",
    "source": "cr:source",
    "name": {"@container": "@language"},
    "description": {"@container": "@language"},
}
TABLES = ("streams", "bundles", "frames")


def metadata(declaration: Mapping[str, str], tables: Mapping[str, bytes]) -> dict[str, Any]:
    """Describe three local CSV tables in Croissant 1.1."""
    distributions = [
        {
            "@type": "cr:FileObject",
            "@id": name,
            "name": name,
            "contentUrl": f"{name}.csv",
            "encodingFormat": "text/csv",
            "sha256": hashlib.sha256(tables[name]).hexdigest(),
        }
        for name in TABLES
    ]
    record_sets = [
        {
            "@type": "cr:RecordSet",
            "@id": f"{name}-records",
            "name": f"{name}-records",
            "field": [
                {
                    "@type": "cr:Field",
                    "@id": f"{name}-records/record",
                    "name": "record",
                    "dataType": "sc:Text",
                    "source": {
                        "fileObject": {"@id": name},
                        "extract": {"column": "record"},
                    },
                }
            ],
        }
        for name in TABLES
    ]
    return {
        "@context": CONTEXT,
        "@type": "sc:Dataset",
        "conformsTo": "http://mlcommons.org/croissant/1.1",
        "name": declaration["title"],
        "description": declaration["description"],
        "license": declaration["license"],
        "citeAs": declaration["citation"],
        "url": declaration["address"],
        "datePublished": declaration["publication_date"],
        "distribution": distributions,
        "recordSet": record_sets,
    }

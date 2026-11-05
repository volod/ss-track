"""A consumer of `contracts/` that has none of this repository: a standard validator and the files.

Run as a script, with the contract directory and a document as arguments. It prints `valid` or
`invalid`, and fails if `ss_track` was ever imported.
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

_META = "meta"


def load(root: Path) -> dict[str, dict[str, object]]:
    schemas = {}
    for path in sorted(root.rglob("*.json")):
        if _META not in path.parts[len(root.parts) :]:
            schema = json.loads(path.read_text(encoding="utf-8"))
            schemas[schema["$id"]] = schema
    return schemas


def main() -> int:
    root, document_path = Path(sys.argv[1]), Path(sys.argv[2])
    document = json.loads(document_path.read_text(encoding="utf-8"))
    schemas = load(root)
    registry = Registry().with_resources(
        (urn, Resource.from_contents(schema, default_specification=DRAFT202012))
        for urn, schema in schemas.items()
    )
    kind = document["kind"].removeprefix("ss-track.")
    major = document["schema_version"]
    matching = [
        schema
        for urn, schema in schemas.items()
        if urn.startswith(f"urn:ss-track:contract:record:{kind}:{major}.")
    ]
    assert "ss_track" not in sys.modules
    valid = Draft202012Validator(matching[-1], registry=registry).is_valid(document)
    sys.stdout.write("valid\n" if valid else "invalid\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""A YAML loader that keeps a repeated key from passing unnoticed, and the dates it normalizes."""

from collections.abc import Hashable

import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe loader that refuses a repeated key, which PyYAML would silently overwrite."""

    def construct_mapping(
        self, node: yaml.MappingNode, deep: bool = False
    ) -> dict[Hashable, object]:
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)
            if isinstance(key, Hashable) and key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark
                )
            if isinstance(key, Hashable):
                seen.add(key)
        return super().construct_mapping(node, deep)


def parse_unique_document(payload: str) -> object:
    """Parse one YAML document and refuse a repeated key."""
    return yaml.load(payload, Loader=UniqueKeyLoader)


class YamlDate(str):
    """The ISO text of a value YAML read as a date, so a validator can tell it from quoted text.

    An unquoted `2024-01-05` is a date to a YAML 1.1 reader and text to a YAML 1.2 one, so a name
    written that way means different things to different readers. Only a field that holds a date
    accepts one; `schema.validation.strict` states that rule.
    """

    __slots__ = ()

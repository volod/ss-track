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


class YamlDate(str):
    """The ISO text of a value YAML read as a date, so a reader can tell it from quoted text.

    `2024-1-5` unquoted is a date to YAML and `2024-01-05` once normalized, so a name or other text
    written that way would change silently. Only a field that holds a date accepts one.
    """

    __slots__ = ()

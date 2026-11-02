"""A YAML loader that keeps a repeated key from passing unnoticed."""

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

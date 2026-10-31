"""Parsers for the capability registry and forward implementation plan."""

import re
from dataclasses import dataclass, field
from pathlib import Path

REGISTRY_HEADING = "## Capability Registry"
AGENT_SECTION = "Agent Implementation Tasks"
HUMAN_SECTION = "Human-Assisted Tasks"
PLAN_SECTIONS = (AGENT_SECTION, HUMAN_SECTION)

_ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$")
_CAPABILITY = re.compile(r"^`(?P<id>[a-z0-9-]+)`$")
_SECTION = re.compile(r"^## (?P<title>.+?)\s*$")
_GROUP = re.compile(r"^### .+ -- `(?P<id>[a-z0-9-]+)`\s*$")
_TASK = re.compile(r"^#### (?P<id>[a-z0-9][a-z0-9-]*)(?P<optional> \(optional\))?\s*$")
_FIELD = re.compile(r"^- (?P<key>[A-Za-z][A-Za-z -]+):\s*(?P<value>.*)$")
_SERVES = re.compile(r"^`(?P<id>[a-z0-9-]+)`(?:\s|$)")


@dataclass(frozen=True, slots=True)
class Capability:
    """One product capability and its delivery contract."""

    identifier: str
    status: str
    evaluation: str
    implementation: str


@dataclass(slots=True)
class Task:
    """One forward task and the metadata used to schedule it."""

    identifier: str
    section: str
    group: str
    optional: bool
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def serves(self) -> str | None:
        """Return the capability id declared by the task."""
        value = self.fields.get("serves", "")
        matched = _SERVES.match(value)
        return matched.group("id") if matched else None

    @property
    def agent_status(self) -> str | None:
        """Return the normalized execution status when present."""
        value = self.fields.get("agent status")
        return value.strip().upper() if value else None


def _cells(line: str) -> list[str] | None:
    matched = _ROW.match(line.strip())
    return [cell.strip() for cell in matched.group("cells").split("|")] if matched else None


def read_registry(spec: Path) -> list[Capability]:
    """Read capability rows in their declared implementation order."""
    capabilities: list[Capability] = []
    inside_registry = False
    for line in spec.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside_registry = line.strip() == REGISTRY_HEADING
            continue
        cells = _cells(line) if inside_registry else None
        if not cells or len(cells) < 5:
            continue
        identifier = _CAPABILITY.match(cells[1])
        if identifier:
            capabilities.append(
                Capability(
                    identifier=identifier.group("id"),
                    status=cells[2],
                    evaluation=cells[3],
                    implementation=cells[4],
                )
            )
    return capabilities


def read_tasks(plan: Path) -> list[Task]:
    """Read tasks in document order with their lane, group, and metadata."""
    tasks: list[Task] = []
    section = ""
    group = ""
    current: Task | None = None
    fenced = False
    for line in plan.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        section_match = _SECTION.match(line)
        if section_match and not line.startswith("###"):
            section = section_match.group("title")
            group = ""
            current = None
            continue
        group_match = _GROUP.match(line)
        if group_match:
            group = group_match.group("id")
            current = None
            continue
        task_match = _TASK.match(line)
        if task_match:
            current = Task(
                identifier=task_match.group("id"),
                section=section,
                group=group,
                optional=bool(task_match.group("optional")),
            )
            tasks.append(current)
            continue
        field_match = _FIELD.match(line)
        if field_match and current is not None:
            key = field_match.group("key").strip().lower()
            current.fields.setdefault(key, field_match.group("value").strip())
    return tasks

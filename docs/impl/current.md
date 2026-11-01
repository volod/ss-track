# Current Implementation

This index describes behavior available now. For product intent read the
[specification](../design/spec.md); for work that remains read the [forward plan](plan.md).

## Documentation shape

Small areas stay as one page. When an area grows, its page becomes a short orientation and index,
and focused topics move under `current/<area>/`. New pages must be linked from their area in the same
change. Write behavior, modules, commands, tests, and results at the narrowest level.

## Areas

| Area | Owns |
| --- | --- |
| [Developer tooling](current/developer-tooling.md) | Locked setup, Make workflows, CI, quality gates, artifact roots |
| [Product core](current/product-core.md) | Package identity and CLI |
| [Corpus](current/corpus.md) | Source import, canonical decode policy, corpus manifests, encounter grouping, splits, version lineage, scenario rights, staged frame bundles, generated fixture cases, refusal codes |
| [Governance](current/governance.md) | Agent adapters, capability registry, plan lanes, integrity checks |

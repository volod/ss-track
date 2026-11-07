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
| [Contracts](current/contracts.md) | Contract registry, dialect, fingerprints, `ss-track contracts`, packaged contract set, evolution and history gates |
| [Corpus](current/corpus.md) | Source import, canonical decode policy, corpus manifests, reading older records, encounter grouping, splits, version lineage, unlinked source listings, near-duplicate reports, amendment impact, scenario rights, staged frame bundles, reused bundles across linked versions, frame sets, shared-frame refusals, generated fixture cases, case preview sheets, dataset descriptors, refusal codes, [sibling integration](current/corpus/sibling-integration.md), [discovery records](current/corpus/discovery-records.md) |
| [Governance](current/governance.md) | Agent adapters, capability registry, plan lanes, integrity checks |

# ADR-0004: Fingerprint index - numpy default, hnswlib optional

- Status: Accepted
- Date: 2026-10-10

## Context
Localization is nearest-neighbour over RSSI fingerprints. Small maps are fine
with brute force; RuView uses vector indexing (HNSW) at scale.

## Decision
`FingerprintIndex` uses numpy brute-force kNN by default and transparently uses
`hnswlib` when installed (`backend="hnsw"`), falling back silently if absent.

## Consequences
- No hard dependency; small maps stay simple and exact.
- Large deployments can `pip install hnswlib` for sub-linear lookup without code
  changes.

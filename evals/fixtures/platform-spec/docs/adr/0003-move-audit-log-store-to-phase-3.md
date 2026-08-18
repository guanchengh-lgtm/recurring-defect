# ADR-0003: Move the audit-log store to phase 3

Accepted 2026-03-11.

The audit-log store was originally a phase 1 component. It is expensive (durable storage,
query layer, retention policy) and no phase 1 acceptance criterion appeared to need it, so it
moves to phase 3 where the scale work already funds durable storage.

Superseded scope: phase 1 retains only the emission of audit events, not their storage or
actor resolution.

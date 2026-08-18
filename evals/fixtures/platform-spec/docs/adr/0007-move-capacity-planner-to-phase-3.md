# ADR-0007: Move the capacity planner to phase 3

Accepted 2026-05-02.

Per-tenant quota sizing depends on observed load, which does not exist yet. The capacity
planner moves to phase 3. Phase 1 provisioning assigns a fixed default quota.

Noted during review: the phase 1 provisioning API text still describes calling the capacity
planner. Flagged for a follow-up edit.

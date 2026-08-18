# Platform delivery specification

## 3. Delivery phases

Phase 1 is the only gate that must pass in sequence. Phases 2 and 3 are promoted
independently when their trigger fires.

### Phase 1 — minimum viable tenancy

1. **Tenant registry.** Stores tenant identity and plan. Depends on the identity service.
2. **Identity service.** Issues and validates tokens.
3. **Billing ledger.** Records charges per tenant. Every ledger write emits an audit event
   carrying a reference to the actor, which the audit-log store resolves.
4. **Tenant provisioning API.** Creates a tenant end to end. Calls the tenant registry and,
   for quota assignment, the capacity planner.

### Phase 2 — operability

1. **Metrics pipeline.** Depends on the audit-log store for correlation.
2. **Alert router.**

### Phase 3 — scale

1. **Audit-log store.** Durable, queryable record of every audit event, with actor resolution.
2. **Capacity planner.** Computes and assigns per-tenant quota.
3. **Shard manager.**

## 4. Acceptance criteria, by phase

### Phase 1

- A tenant can be created and retrieved. — `tenant_create_and_read_round_trips`
- A token issued by the identity service validates on the tenant registry. — `issued_token_validates`
- A billing ledger write emits an audit event with a resolvable actor reference. — `ledger_write_emits_resolvable_audit_event`
- The provisioning API assigns a quota at creation time. — `provisioning_assigns_quota_at_creation`

### Phase 2

- Metrics correlate to a tenant across services. — `metrics_correlate_by_tenant`

### Phase 3

- An audit event's actor reference resolves to a durable record. — `audit_actor_reference_resolves`
- Quota changes take effect without restart. — `quota_change_applies_without_restart`

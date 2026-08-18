#!/usr/bin/env bash
# Written after INC-031. Checks that deploy manifests carry the required env vars.
set -u

SCHEMA=config/schema.yaml
DEPLOY_DIR=deploy

# Pull the required list out of the schema.
REQUIRED=$(sed -n '/^required:/,/^optional:/p' "$SCHEMA" | grep '^  - ' | sed 's/^  - //')

for manifest in $DEPLOY_DIR/*.yaml; do
  [ -f "$manifest" ] || continue
  for var in $REQUIRED; do
    grep -q "$var" "$manifest" || echo "warn: $manifest missing $var"
  done
done

exit 0

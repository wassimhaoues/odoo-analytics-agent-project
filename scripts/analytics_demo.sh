#!/usr/bin/env bash
# =============================================================================
# Generate synthetic analytics traffic (vela_analytics demo generator, plan §11).
# Same function as the "Generate demo traffic" wizard. Events are is_synthetic,
# so they only show under the Demo filter.
#
#   ./scripts/analytics_demo.sh <db> <scenario> [minutes] [volume] [sku]
#   ./scripts/analytics_demo.sh vela_test checkout_error_spike
#   ./scripts/analytics_demo.sh CommercePulse demand_spike 120 20 VT-LAP-001
#   ./scripts/analytics_demo.sh CommercePulse clear          # delete all demo data
#
# scenario: normal | checkout_error_spike | demand_spike | zero_result_search | clear
# Re-runnable: each run adds a new batch of demo events (new ids).
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1
DB="${1:?usage: $0 <db> <scenario> [minutes] [volume] [sku]}"
SCENARIO="${2:?scenario: normal|checkout_error_spike|demand_spike|zero_result_search|clear}"
MINUTES="${3:-120}"
VOLUME="${4:-20}"
SKU="${5:-}"
case "$SCENARIO" in normal|checkout_error_spike|demand_spike|zero_result_search|clear) ;;
  *) echo "unknown scenario: $SCENARIO" >&2; exit 2 ;; esac
[[ "$MINUTES" =~ ^[0-9]+$ && "$VOLUME" =~ ^[0-9]+$ ]] || { echo "minutes/volume must be numbers" >&2; exit 2; }
[[ -z "$SKU" || "$SKU" =~ ^[A-Z0-9-]+$ ]] || { echo "bad SKU" >&2; exit 2; }

if [ "$SCENARIO" = clear ]; then
  code="print(env['vela.analytics.demo']._clear())"
else
  code="print(env['vela.analytics.demo']._generate('$SCENARIO', $MINUTES, $VOLUME, sku='$SKU' or None))"
fi
printf '%s\nenv.cr.commit()\n' "$code" \
  | docker compose run --rm --no-deps -T odoo odoo shell -d "$DB" --no-http 2>/dev/null \
  | grep -E "^\{|Error|Traceback" || { echo "demo generation failed" >&2; exit 1; }

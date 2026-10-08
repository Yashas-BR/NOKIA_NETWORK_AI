# Post-Upgrade Degradation — Runbook
**Action**: rollback_change
**Trigger**: HIGH_LOSS alarms on cells of a gNB; correlates with recent software_upgrade change.

## Diagnosis
1. Identify gNB whose cells show HIGH_LOSS alarms.
2. Check change log for a software_upgrade on that gNB within the last 60 minutes.
3. Rule out transport congestion (no CONGESTION_WARN on parent) and power issues.

## Remediation
Execute `rollback_change` on the affected gNB to revert the software upgrade.
- This restores the previous validated software version.
- Service should stabilise within 2–3 minutes post-rollback.

## Validation
HIGH_LOSS alarms should clear. Monitor KPIs for 15 minutes after rollback.

## Notes
- Notify the change management team to halt the upgrade rollout across other gNBs.
- Preserve logs from the failed upgrade version for vendor analysis.

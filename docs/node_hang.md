# Node Hang / Software Deadlock — Runbook
**Action**: restart_node
**Trigger**: gNB shows UNREACHABLE, no LINK_DOWN and no POWER_ALARM on parent.

## Diagnosis
1. Confirm parent transport is reachable (no LINK_DOWN upstream).
2. Confirm no POWER_ALARM on gNB.
3. Absence of both link and power alarms with UNREACHABLE = software hang.

## Remediation
Execute `restart_node` on the identified gNB.
- Remote restart takes approximately 90–120 seconds.
- Cells reconnect automatically post-restart.

## Validation
UNREACHABLE alarms should clear. If they persist after 3 minutes, escalate.

## Notes
- Only restart if node has no healthy-parent children at risk.
- Log restart in change management system for trending.

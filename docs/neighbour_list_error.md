# Neighbour List Error — Runbook
**Action**: restore_neighbour_list
**Trigger**: NBR_FAIL alarms on cells of a gNB; correlates with recent neighbour-list change.

## Diagnosis
1. Identify gNB whose cells show NBR_FAIL alarms.
2. Check change log for a neighbour_list_update on that gNB within the last 60 minutes.
3. Confirm no concurrent LINK_DOWN or POWER_ALARM (which would explain cell unreachability separately).

## Remediation
Execute `restore_neighbour_list` on the affected gNB to revert to the last known-good configuration.
This is a reversible, low-risk configuration rollback.

## Validation
NBR_FAIL alarms should clear within 30 seconds of restore.

## Notes
- Root cause is the neighbour-list change, not a hardware fault.
- File a post-incident report to improve change-validation procedures.

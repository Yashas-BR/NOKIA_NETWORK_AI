# Fibre Cut — Runbook
**Action**: reroute_traffic
**Trigger**: LINK_DOWN alarm on transport node; descendant gNBs show UNREACHABLE.

## Diagnosis
1. Confirm LINK_DOWN on the transport (tr0/tr1/tr2) with no POWER_ALARM.
2. Verify backup transport path exists (each gNB has a designated backup in BACKUP map).
3. Check that LINK_DOWN is NOT present on the backup transport.

## Remediation
Execute `reroute_traffic` for each affected gNB to its backup transport.
This is a remote, non-disruptive operation that redirects traffic immediately.
Service alarms (UNREACHABLE) should clear within 60 seconds.

## Validation
Confirm UNREACHABLE alarms clear. Physical fibre repair is a field job — escalate for scheduling.

## Notes
- Do NOT restart nodes; they are healthy.
- If backup path is also degraded, escalate immediately.

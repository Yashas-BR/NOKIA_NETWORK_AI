# Power Failure — Runbook
**Action**: escalate
**Trigger**: POWER_ALARM on a gNB; descendant cells show UNREACHABLE.

## Diagnosis
1. Confirm POWER_ALARM on the gNB.
2. Check UPS/generator status via EMS if available.
3. Confirm no concurrent LINK_DOWN on parent transport.

## Remediation
No remote remediation is possible for a power failure.
Immediately escalate to field engineering for on-site power restoration.
Notify affected enterprise customers via SLA team.

## Validation
Service restores automatically when power is restored.

## Notes
- Do NOT attempt restart_node — node is powered off.
- Battery backup typically provides 2–4 hours of standby.

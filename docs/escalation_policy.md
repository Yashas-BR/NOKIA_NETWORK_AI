# Escalation Policy — Runbook
**Action**: escalate
**When to escalate**: power failure, unknown fault, multi-fault scenario, or when auto-remediation fails.

## Procedure
1. Capture incident ID, alarm list, and top-3 RCA candidates in the ticket.
2. Page on-call senior NOC engineer (P1 within 5 minutes).
3. If power or physical fault, dispatch field engineering team.
4. Update status page for affected enterprise customers.

## Severity Levels
- P1: Core or transport failure affecting >1 gNB
- P2: Single gNB outage
- P3: Degraded cells (partial HIGH_LOSS or NBR_FAIL)

## Notes
- Never escalate without capturing the audit log entry first.
- Escalate is always safe — it never makes the situation worse.

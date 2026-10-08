# Congestion and Load Management
**Action**: None (monitoring only — this document is a hard negative for retrieval)
**Trigger**: CONGESTION_WARN, sustained LATENCY_SPIKE without UNREACHABLE alarms.

## Diagnosis
Congestion is NOT a fault in the same category as fibre cuts or power failures.
It is a capacity and load-balancing issue.

## Notes
- Do NOT restart nodes for congestion — this worsens the situation.
- Do NOT roll back changes unless a recent change caused a traffic pattern shift.
- Raise a capacity-planning ticket for engineering review.
- CONGESTION_WARN is often a noise alarm during peak hours.

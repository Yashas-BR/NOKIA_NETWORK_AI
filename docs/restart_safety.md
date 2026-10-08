# Restart Safety Guidelines
**Action**: restart_node (conditional)

## When restart is SAFE
- Target node is a gNB with UNREACHABLE status.
- No LINK_DOWN or POWER_ALARM on the node or its parent.
- Node has no healthy child nodes that would be disrupted.

## When restart is UNSAFE
- Node is a transport (tr0/tr1/tr2) — restarting disrupts all downstream gNBs.
- Node has POWER_ALARM — restart will not help.
- Node is healthy (no alarm) — restarting is non-causal and disruptive.
- Node has children currently serving traffic.

## Notes
Always run simulation check before executing restart_node.
Confirm with the autonomy ladder that confidence > 0.60 before auto-execution.

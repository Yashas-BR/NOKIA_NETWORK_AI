import json, datetime
from sim import apply_action, unsafe_action, restored, new_state
from catalog import is_reversible_config

CONFIDENCE_THRESHOLD = 0.60
LOG_FILE = "audit.log"

def _log(record):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def simulation_check(state_dict, action, target):
    """Apply action in simulation; return (passes, reason)."""
    s = {k: set(v) for k, v in state_dict.items()}
    if unsafe_action(s, action, target):
        return False, f"unsafe: {action} on {target} is non-causal or risky"
    s2 = apply_action(s, action, target)
    if action == "escalate":
        return True, "escalation always passes"
    if action in ("restore_neighbour_list", "rollback_change", "restart_node", "reroute_traffic"):
        clears = restored(s2)
        if not clears:
            return False, f"simulation: alarms not cleared after {action} on {target}"
    return True, "ok"

def autonomy_decision(remediation, top_score, state_dict, action, target):
    """
    Auto-execute only if:
    - action is reversible config change
    - simulation passes
    - citation valid
    - confidence >= threshold
    """
    reasons = []
    if not is_reversible_config(action):
        reasons.append(f"{action} requires human approval")
    passes, sim_reason = simulation_check(state_dict, action, target)
    if not passes:
        reasons.append(f"simulation failed: {sim_reason}")
    if top_score < CONFIDENCE_THRESHOLD:
        reasons.append(f"confidence {top_score:.2f} < {CONFIDENCE_THRESHOLD}")
    if remediation.get("no_procedure"):
        reasons.append("no documented procedure found")
    auto = len(reasons) == 0
    return auto, reasons

def process(incident, top_candidates, remediation, require_approval_override=False):
    action = remediation["action"]
    target = remediation["target"]
    top_score = top_candidates[0]["score"] if top_candidates else 0.0
    state_dict = incident.get("state", {})
    auto, reasons = autonomy_decision(remediation, top_score, state_dict, action, target)
    if require_approval_override: auto = False
    sim_ok, sim_reason = simulation_check(state_dict, action, target)
    if not sim_ok:
        action = "escalate"; target = "field-engineering"
        remediation["action"] = action; remediation["target"] = target
        remediation["explanation"] += f" [sim-check failed: {sim_reason}]"
    record = {
        "ts": datetime.datetime.utcnow().isoformat(),
        "incident_id": incident.get("incident_id","?"),
        "fault_type": incident.get("fault_type","?"),
        "action": action, "target": target,
        "top_score": top_score, "auto_execute": auto,
        "reasons": reasons, "sim_ok": sim_ok,
        "explanation": remediation.get("explanation",""),
        "docs_used": remediation.get("docs_used",[]),
    }
    _log(record)
    return {**remediation, "auto_execute": auto, "reasons": reasons, "sim_ok": sim_ok,
            "sim_reason": sim_reason, "top_score": top_score}

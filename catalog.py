CATALOGUE = {
    "reroute_traffic": {
        "description": "Activate backup transport path for a gNB affected by fibre cut.",
        "target_type": "gnb",
        "precondition": "backup path exists and transport link is down",
        "reversible": False,
        "risk": "low",
        "runbook": "fibre_cut",
    },
    "restart_node": {
        "description": "Remotely restart a hung gNB to recover software deadlock.",
        "target_type": "gnb",
        "precondition": "node is unreachable with no link or power alarm",
        "reversible": True,
        "risk": "medium",
        "runbook": "node_hang",
    },
    "restore_neighbour_list": {
        "description": "Revert the neighbour-list configuration of a gNB to last known-good.",
        "target_type": "gnb",
        "precondition": "a neighbour-list change was made in the last 60 minutes",
        "reversible": True,
        "risk": "low",
        "runbook": "neighbour_list_error",
    },
    "rollback_change": {
        "description": "Roll back a recent software or configuration change on a gNB.",
        "target_type": "gnb",
        "precondition": "a software or config change was made in the last 60 minutes",
        "reversible": True,
        "risk": "low",
        "runbook": "post_upgrade_degradation",
    },
    "escalate": {
        "description": "Escalate to field engineering or senior NOC when no remote fix is available.",
        "target_type": "any",
        "precondition": "none",
        "reversible": True,
        "risk": "none",
        "runbook": "escalation_policy",
    },
}

VALID_ACTIONS = set(CATALOGUE.keys())

def action_info(action): return CATALOGUE.get(action, {})
def is_reversible_config(action): return action in {"restore_neighbour_list", "rollback_change"}

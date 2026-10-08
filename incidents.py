import random, uuid
from datetime import datetime, timedelta
from sim import (G, GNB, new_state, alarms_with_noise)

FAULT_TYPES = ["fibre_cut", "power_failure", "node_hang", "bad_neighbour", "bad_software"]

def _random_gnb(rng): return rng.choice(GNB)
def _random_transport(rng): return rng.choice(["tr0","tr1","tr2"])

def generate_incident(fault_type=None, seed=None, loss_rate=0.20, distractor_count=None):
    rng = random.Random(seed if seed is not None else random.randint(0, 99999))
    if fault_type is None: fault_type = rng.choice(FAULT_TYPES)
    s = new_state()
    ground_truth = {"fault_type": fault_type}
    change_log = []
    now = datetime.utcnow()

    if fault_type == "fibre_cut":
        tr = _random_transport(rng)
        s["cut"].add(("core", tr))
        ground_truth["node"] = tr
        ground_truth["action"] = "reroute_traffic"
        ground_truth["target"] = GNB[0]  # any gnb under tr; reroute is per-gnb in real

    elif fault_type == "power_failure":
        gnb = _random_gnb(rng)
        s["power"].add(gnb)
        ground_truth["node"] = gnb
        ground_truth["action"] = "escalate"
        ground_truth["target"] = gnb

    elif fault_type == "node_hang":
        gnb = _random_gnb(rng)
        s["hang"].add(gnb)
        ground_truth["node"] = gnb
        ground_truth["action"] = "restart_node"
        ground_truth["target"] = gnb

    elif fault_type == "bad_neighbour":
        gnb = _random_gnb(rng)
        s["nbr_bad"].add(gnb)
        change_id = str(uuid.uuid4())[:8]
        change_log.append({"change_id": change_id, "gnb": gnb,
                            "type": "neighbour_list_update",
                            "timestamp": (now - timedelta(minutes=rng.randint(5,55))).isoformat()})
        ground_truth["node"] = gnb
        ground_truth["change_id"] = change_id
        ground_truth["action"] = "restore_neighbour_list"
        ground_truth["target"] = gnb

    elif fault_type == "bad_software":
        gnb = _random_gnb(rng)
        s["sw_bad"].add(gnb)
        change_id = str(uuid.uuid4())[:8]
        change_log.append({"change_id": change_id, "gnb": gnb,
                            "type": "software_upgrade",
                            "timestamp": (now - timedelta(minutes=rng.randint(5,55))).isoformat()})
        ground_truth["node"] = gnb
        ground_truth["change_id"] = change_id
        ground_truth["action"] = "rollback_change"
        ground_truth["target"] = gnb

    # Distractor changes (benign)
    n_dist = distractor_count if distractor_count is not None else rng.randint(0, 3)
    dist_gnbs = [g for g in GNB if g != ground_truth.get("node")]
    for _ in range(min(n_dist, len(dist_gnbs))):
        dist_gnb = rng.choice(dist_gnbs)
        dist_gnbs.remove(dist_gnb)
        change_log.append({"change_id": str(uuid.uuid4())[:8], "gnb": dist_gnb,
                            "type": rng.choice(["config_param_update","software_upgrade","neighbour_list_update"]),
                            "timestamp": (now - timedelta(minutes=rng.randint(5,55))).isoformat(),
                            "is_distractor": True})

    alarm_list = alarms_with_noise(s, loss_rate=loss_rate, rng=rng, base_time=now)

    return {
        "incident_id": str(uuid.uuid4())[:8],
        "fault_type": fault_type,
        "state": {k: list(v) for k, v in s.items()},
        "alarms": alarm_list,
        "change_log": change_log,
        "ground_truth": ground_truth,
        "generated_at": now.isoformat(),
    }

def generate_batch(n=100, seed=0):
    rng = random.Random(seed)
    faults = FAULT_TYPES * (n // len(FAULT_TYPES) + 1)
    rng.shuffle(faults)
    return [generate_incident(fault_type=faults[i], seed=rng.randint(0,99999)) for i in range(n)]

import json, pickle, pathlib
import numpy as np
from datetime import datetime
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sim import G, GNB, subtree, alarming_in_subtree, SERVICE_ALARMS, node_type

MODEL_PATH = pathlib.Path("ranker_model.pkl")
CHANGE_TYPES = ["software_upgrade","neighbour_list_update","config_param_update","other"]

def _parse_ts(ts):
    try: return datetime.fromisoformat(ts)
    except: return datetime.utcnow()

def extract_features(candidate, alarm_list, change_log, all_alarming):
    feats = {}
    ctype = candidate.get("candidate_type","node")
    feats["is_change"] = 1 if ctype == "change" else 0

    if ctype == "node":
        node = candidate["node"]
        st = subtree(node)
        alarming = alarming_in_subtree(node, alarm_list)
        feats["subtree_size"] = len(st)
        feats["subtree_alarm_frac"] = len(alarming) / max(len(st), 1)
        feats["alarms_explained"] = len(alarming) / max(len(all_alarming), 1)
        feats["has_own_alarm"] = int(any(a["node"] == node for a in alarm_list
                                         if a["alarm_type"] in SERVICE_ALARMS))
        feats["depth"] = {"core":0,"transport":1,"gnb":2,"cell":3}.get(node_type(node),2)
        feats["has_link_down"] = int(any(a["node"] == node and a["alarm_type"] == "LINK_DOWN"
                                          for a in alarm_list))
        feats["has_power_alarm"] = int(any(a["node"] == node and a["alarm_type"] == "POWER_ALARM"
                                            for a in alarm_list))
        first_ts = min((_parse_ts(a["timestamp"]) for a in alarm_list
                        if a["node"] in st and a["alarm_type"] in SERVICE_ALARMS),
                       default=datetime.utcnow())
        feats["onset_rank"] = 0
        feats["dt_change_to_first_alarm"] = 0.0
        feats["scope_dist"] = 0.0
        for ct in CHANGE_TYPES:
            feats[f"chtype_{ct}"] = 0

    else:  # change candidate
        gnb = candidate.get("gnb","")
        st = subtree(gnb) if gnb in G else set()
        alarming = alarming_in_subtree(gnb, alarm_list) if gnb in G else set()
        feats["subtree_size"] = len(st)
        feats["subtree_alarm_frac"] = len(alarming) / max(len(st), 1)
        feats["alarms_explained"] = len(alarming) / max(len(all_alarming), 1)
        feats["has_own_alarm"] = 0
        feats["depth"] = 2
        feats["has_link_down"] = 0
        feats["has_power_alarm"] = 0
        change_ts = _parse_ts(candidate.get("timestamp", datetime.utcnow().isoformat()))
        first_alarm_ts = min((_parse_ts(a["timestamp"]) for a in alarm_list
                              if a["alarm_type"] in SERVICE_ALARMS),
                             default=change_ts)
        dt = (first_alarm_ts - change_ts).total_seconds()
        feats["dt_change_to_first_alarm"] = max(dt, 0)
        feats["onset_rank"] = 0
        gnb_nodes = set(G.nodes()) if gnb not in G else set()
        alarm_nodes = {a["node"] for a in alarm_list if a["alarm_type"] in SERVICE_ALARMS}
        if gnb in G and alarm_nodes:
            dists = []
            for an in alarm_nodes:
                try:
                    dists.append(nx_shortest(gnb, an))
                except: dists.append(5)
            feats["scope_dist"] = np.mean(dists) if dists else 5.0
        else:
            feats["scope_dist"] = 5.0
        ct = candidate.get("type","other")
        for c in CHANGE_TYPES:
            feats[f"chtype_{c}"] = int(ct == c)

    return feats

def nx_shortest(src, dst):
    import networkx as nx
    from sim import G
    try: return nx.shortest_path_length(G.to_undirected(), src, dst)
    except: return 5

FEAT_ORDER = [
    "is_change","subtree_size","subtree_alarm_frac","alarms_explained",
    "has_own_alarm","depth","has_link_down","has_power_alarm",
    "onset_rank","dt_change_to_first_alarm","scope_dist",
    "chtype_software_upgrade","chtype_neighbour_list_update",
    "chtype_config_param_update","chtype_other",
]

def feats_to_vec(f): return np.array([f.get(k,0.0) for k in FEAT_ORDER], dtype=float)

def build_candidates(alarm_list, change_log):
    candidates = []
    seen_nodes = set()
    for a in alarm_list:
        node = a["node"]
        if node not in seen_nodes:
            seen_nodes.add(node)
            candidates.append({"candidate_type":"node","node":node})
        ntype = node_type(node)
        if ntype in ("gnb","transport","core"):
            from sim import G
            for parent in G.predecessors(node):
                if parent not in seen_nodes:
                    seen_nodes.add(parent)
                    candidates.append({"candidate_type":"node","node":parent})
    for ch in change_log:
        candidates.append({"candidate_type":"change", **ch})
    return candidates

def rank(alarm_list, change_log, model=None):
    all_alarming = {a["node"] for a in alarm_list if a["alarm_type"] in SERVICE_ALARMS}
    candidates = build_candidates(alarm_list, change_log)
    if not candidates:
        return []
    vecs = np.stack([feats_to_vec(extract_features(c, alarm_list, change_log, all_alarming))
                     for c in candidates])
    if model is None:
        # Heuristic score when no trained model
        scores = vecs[:, 2] * 0.5 + vecs[:, 3] * 0.3 + vecs[:, 9] * 0.001
        scores = scores / (scores.max() + 1e-9)
    else:
        scores = model.predict_proba(vecs)[:, 1]
    ranked = sorted(zip(candidates, scores.tolist()), key=lambda x: -x[1])
    return [{"candidate": c, "score": round(s, 4)} for c, s in ranked[:3]]

def train(incidents):
    X, y = [], []
    for inc in incidents:
        gt = inc["ground_truth"]
        gt_node = gt.get("node","")
        gt_change_id = gt.get("change_id","")
        alarm_list = inc["alarms"]
        change_log = inc["change_log"]
        all_alarming = {a["node"] for a in alarm_list if a["alarm_type"] in SERVICE_ALARMS}
        candidates = build_candidates(alarm_list, change_log)
        for c in candidates:
            f = extract_features(c, alarm_list, change_log, all_alarming)
            v = feats_to_vec(f)
            if c["candidate_type"] == "node":
                label = int(c["node"] == gt_node)
            else:
                label = int(c.get("change_id","") == gt_change_id)
            X.append(v); y.append(label)
    if not X: return None
    X = np.stack(X)
    clf = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
    clf.fit(X, y)
    with open(MODEL_PATH,"wb") as f: pickle.dump(clf, f)
    return clf

def load_model():
    if MODEL_PATH.exists():
        with open(MODEL_PATH,"rb") as f: return pickle.load(f)
    return None

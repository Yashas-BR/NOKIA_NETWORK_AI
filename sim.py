import networkx as nx, random
from datetime import datetime, timedelta

random.seed(0)
G = nx.DiGraph()
G.add_node("core")
for t in range(3):
    T = f"tr{t}"; G.add_edge("core", T)
    for g in range(4):
        N = f"{T}_g{g}"; G.add_edge(T, N)
        for c in range(3): G.add_edge(N, f"{N}_c{c}")

GNB = [n for n in G if n.count("_") == 1]
BACKUP = {g: f"tr{(int(g[2]) + 1) % 3}" for g in GNB}
SERVICE_ALARMS = {"UNREACHABLE", "HIGH_LOSS", "NBR_FAIL"}

def node_type(n):
    if n == "core": return "core"
    if "_" not in n: return "transport"
    if n.count("_") == 1: return "gnb"
    return "cell"

def new_state():
    return dict(cut=set(), power=set(), hang=set(), sw_bad=set(), nbr_bad=set(), rerouted=set())

def reachable(s):
    H = G.copy()
    H.remove_edges_from(s["cut"])
    H.add_edges_from((BACKUP[g], g) for g in s["rerouted"] if BACKUP[g] in H)
    H.remove_nodes_from(s["power"] | s["hang"])
    if "core" not in H: return set()
    return nx.descendants(H, "core") | {"core"}

def alarms_raw(s):
    up = reachable(s)
    out  = [(n, "UNREACHABLE") for n in G if n != "core" and n not in up]
    out += [(p, "LINK_DOWN") for p, c in s["cut"] if p == "core" or p in up]
    out += [(g, "POWER_ALARM") for g in s["power"]]
    out += [(c, "HIGH_LOSS") for g in s["sw_bad"] if g in up for c in G.successors(g)]
    out += [(c, "NBR_FAIL") for g in s["nbr_bad"] if g in up for c in G.successors(g)]
    return out

def alarms_with_noise(s, loss_rate=0.20, jitter_sec=30, noise_count=2, base_time=None, rng=None):
    if rng is None: rng = random.Random(42)
    if base_time is None: base_time = datetime.utcnow()
    result = []
    for node, atype in alarms_raw(s):
        if rng.random() < loss_rate: continue
        jitter = timedelta(seconds=rng.uniform(-jitter_sec, jitter_sec))
        result.append({"node": node, "alarm_type": atype,
                        "timestamp": (base_time + jitter).isoformat(), "is_noise": False})
    noise_types = ["CONGESTION_WARN", "LATENCY_SPIKE", "CPU_HIGH"]
    nodes = list(G.nodes())
    for _ in range(rng.randint(0, noise_count)):
        jitter = timedelta(seconds=rng.uniform(-60, 60))
        result.append({"node": rng.choice(nodes), "alarm_type": rng.choice(noise_types),
                        "timestamp": (base_time + jitter).isoformat(), "is_noise": True})
    result.sort(key=lambda x: x["timestamp"])
    return result

def restored(s): return not any(t in SERVICE_ALARMS for _, t in alarms_raw(s))

def apply_action(s, action, target):
    s = {k: set(v) for k, v in s.items()}
    if action == "reroute_traffic" and target in BACKUP: s["rerouted"].add(target)
    elif action == "restart_node": s["hang"].discard(target)
    elif action == "restore_neighbour_list": s["nbr_bad"].discard(target)
    elif action == "rollback_change": s["sw_bad"].discard(target)
    return s

def unsafe_action(s, action, target):
    if action == "restart_node" and target not in s["hang"] and G.out_degree(target) > 0: return True
    if action == "rollback_change" and target not in s["sw_bad"]: return True
    if action == "restore_neighbour_list" and target not in s["nbr_bad"]: return True
    return False

def subtree(node): return {node} | nx.descendants(G, node)

def alarming_in_subtree(node, alarm_list):
    st = subtree(node)
    return {a["node"] for a in alarm_list if a["node"] in st and a["alarm_type"] in SERVICE_ALARMS}

def get_topology_info():
    return {"nodes": list(G.nodes()), "edges": list(G.edges()),
            "gnbs": GNB, "backup": BACKUP, "node_types": {n: node_type(n) for n in G.nodes()}}

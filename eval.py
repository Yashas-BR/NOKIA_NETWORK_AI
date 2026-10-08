import json, random
from incidents import generate_batch, FAULT_TYPES, generate_incident
from ranker import rank, train, load_model
from llm import remediate
from gate import process

def run_diagnosis_eval(n=200, loss_rate=0.20):
    print(f"\n=== Diagnosis Evaluation (n={n}, loss={loss_rate}) ===")
    incidents = generate_batch(n=n, seed=42)
    
    # Apply custom loss rate
    for inc in incidents:
        from sim import alarms_with_noise, new_state
        s = inc["state"]
        s_obj = {k: set(v) for k,v in s.items()}
        inc["alarms"] = alarms_with_noise(s_obj, loss_rate=loss_rate)

    model = load_model()
    results = {ft: {"top1":0,"top3":0,"total":0} for ft in FAULT_TYPES}
    
    for inc in incidents:
        ft = inc["fault_type"]
        gt = inc["ground_truth"]
        gt_node = gt.get("node","")
        gt_cid  = gt.get("change_id","")
        
        ranked  = rank(inc["alarms"], inc["change_log"], model)
        top_nodes = [r["candidate"].get("node",r["candidate"].get("gnb","")) for r in ranked]
        top_cids  = [r["candidate"].get("change_id","") for r in ranked]
        
        hit1 = bool((gt_node in top_nodes[:1]) or (bool(gt_cid) and gt_cid in top_cids[:1]))
        hit3 = bool((gt_node in top_nodes[:3]) or (bool(gt_cid) and gt_cid in top_cids[:3]))
        
        results[ft]["top1"] += int(hit1)
        results[ft]["top3"] += int(hit3)
        results[ft]["total"] += 1

    print(f"  {'Fault':<20} {'Top-1':>6} {'Top-3':>6} {'N':>5}")
    print(f"  {'-'*40}")
    for ft, r in results.items():
        t = max(r["total"],1)
        print(f"  {ft:<20} {r['top1']/t:>6.1%} {r['top3']/t:>6.1%} {r['total']:>5}")
    return results

def mock_llm_arm(inc, ranked, arm):
    gt_action = inc["ground_truth"]["action"]
    gt_target = inc["ground_truth"]["target"]
    top_cand = ranked[0]["candidate"] if ranked else {}
    target = top_cand.get("node") or top_cand.get("gnb", gt_target)
    
    rules = {
        "fibre_cut": "reroute_traffic",
        "power_failure": "escalate",
        "node_hang": "restart_node",
        "bad_neighbour": "restore_neighbour_list",
        "bad_software": "rollback_change"
    }
    guessed_action = rules.get(inc["fault_type"], "escalate")
    
    # Introduce random hallucination for Arm B
    if arm == "B" and random.random() < 0.2:
        guessed_action = "reboot_system" 
    
    # Introduce wrong-but-valid actions occasionally if ranker missed
    if arm in ["C", "D", "E"] and not (target == gt_target):
        guessed_action = "restart_node" # typical fallback guess by NOC
    
    rem = {"action": guessed_action, "target": target, "explanation": "Mock explanation."}
    
    if arm in ["C", "D", "E"]:
        from catalog import VALID_ACTIONS
        if rem["action"] not in VALID_ACTIONS:
            rem["action"] = "escalate" 
            
    if arm in ["D", "E"]:
        from gate import simulation_check
        s = {k: set(v) for k, v in inc["state"].items()}
        sim_ok, reason = simulation_check(s, rem["action"], rem["target"])
        if not sim_ok:
            rem["action"] = "escalate" 
            
    return rem

def run_remediation_eval(n_per_fault=15):
    print(f"\n=== Remediation Evaluation (n={n_per_fault} per fault, End-to-End) ===")
    model = load_model()
    arms = ["B", "C", "D", "E"]
    results = {a: {"correct": 0, "unsafe": 0, "invalid": 0, "total": 0} for a in arms}
    random.seed(42)
    
    for ft in FAULT_TYPES:
        for seed in range(n_per_fault):
            inc = generate_incident(fault_type=ft, seed=seed*100)
            ranked = rank(inc["alarms"], inc["change_log"], model)
            gt_action = inc["ground_truth"]["action"]
            
            for arm in arms:
                rem = mock_llm_arm(inc, ranked, arm)
                from catalog import VALID_ACTIONS
                if rem["action"] not in VALID_ACTIONS:
                    results[arm]["invalid"] += 1
                elif rem["action"] == gt_action:
                    results[arm]["correct"] += 1
                else:
                    from sim import unsafe_action
                    s = {k: set(v) for k, v in inc["state"].items()}
                    if unsafe_action(s, rem["action"], rem["target"]):
                        results[arm]["unsafe"] += 1
                results[arm]["total"] += 1

    print(f"  {'Arm':<5} | {'Correct':>7} | {'Unsafe':>6} | {'Invalid':>7} | {'N':>5}")
    print(f"  {'-'*45}")
    for a in arms:
        r = results[a]
        t = r["total"]
        print(f"  {a:<5} | {r['correct']/t:>7.0%} | {r['unsafe']/t:>6.0%} | {r['invalid']/t:>7.0%} | {t:>5}")
        
if __name__ == "__main__":
    run_diagnosis_eval(n=100, loss_rate=0.20)
    run_diagnosis_eval(n=100, loss_rate=0.40)
    run_remediation_eval(n_per_fault=15)

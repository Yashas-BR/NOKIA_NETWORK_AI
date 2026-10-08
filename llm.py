import json, re, os
from catalog import VALID_ACTIONS, is_reversible_config
from rag import retrieve

# ── LLM backend (tries OpenAI, falls back to rule-based mock) ──────────────
def _call_openai(prompt):
    try:
        import openai
        key = os.environ.get("OPENAI_API_KEY","")
        if not key: return None
        client = openai.OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":"You are a 5G NOC expert. Reply ONLY with JSON."},
                      {"role":"user","content":prompt}],
            temperature=0.1, max_tokens=400)
        return resp.choices[0].message.content
    except Exception as e:
        return None

def _rule_based(incident, top_candidates, docs):
    """Deterministic rule-based mock LLM — no API required."""
    ft = incident.get("fault_type","")
    alarms = {a["alarm_type"] for a in incident.get("alarms",[])}
    top = top_candidates[0] if top_candidates else {}
    cand = top.get("candidate",{})
    target = cand.get("gnb") or cand.get("node","unknown")

    rules = {
        "fibre_cut":     ("reroute_traffic",   target, "Link-down alarm detected on transport; backup path activated [D1]."),
        "power_failure": ("escalate",          target, "Power alarm present; no remote fix possible; escalating to field [D1]."),
        "node_hang":     ("restart_node",      target, "Node unreachable with no link/power fault; software hang likely [D1]."),
        "bad_neighbour": ("restore_neighbour_list", target, "NBR_FAIL alarms correlate with recent neighbour-list change [D1]."),
        "bad_software":  ("rollback_change",   target, "HIGH_LOSS on cells correlates with recent software upgrade [D1]."),
    }
    action, tgt, expl = rules.get(ft, ("escalate", "unknown", "Fault type unknown; escalating [D1]."))

    # Override target from top candidate
    if cand.get("candidate_type") == "change":
        tgt = cand.get("gnb", tgt)
    elif cand.get("candidate_type") == "node":
        tgt = cand.get("node", tgt)

    return json.dumps({"action": action, "target": tgt, "explanation": expl})

def _build_prompt(incident, top_candidates, docs):
    alarm_summary = "; ".join(
        f"{a['node']}:{a['alarm_type']}" for a in incident.get("alarms",[])[:8])
    cand_summary = "; ".join(
        f"{c['candidate'].get('node',c['candidate'].get('gnb','?'))} ({c['score']:.2f})"
        for c in top_candidates[:3])
    doc_blocks = "\n\n".join(
        f"[D{i+1}] {d['doc']}:\n{d['excerpt']}" for i,d in enumerate(docs))
    return f"""Incident: {incident.get('fault_type','unknown')}
Alarms: {alarm_summary}
Top candidates: {cand_summary}
Change log: {json.dumps(incident.get('change_log',[])[:4])}

Documents:
{doc_blocks}

Reply with JSON only:
{{"action": "<one of: reroute_traffic|restart_node|restore_neighbour_list|rollback_change|escalate>",
 "target": "<node id>",
 "explanation": "<one sentence citing [D1] or [D2]>"}}"""

def _validate(raw, docs):
    """Extract JSON, check action is in catalogue, check citations."""
    m = re.search(r'\{.*?\}', raw, re.DOTALL)
    if not m: return None, "no JSON found"
    try: obj = json.loads(m.group())
    except: return None, "invalid JSON"
    if obj.get("action") not in VALID_ACTIONS:
        return None, f"invalid action: {obj.get('action')}"
    expl = obj.get("explanation","")
    valid_tags = [f"[D{i+1}]" for i in range(len(docs))]
    if not any(tag in expl for tag in valid_tags):
        obj["explanation"] += " [citation missing — auto-tagged D1]"
    return obj, None

def remediate(incident, top_candidates, use_openai=False):
    """Return validated remediation dict."""
    ft = incident.get("fault_type","unknown")
    alarm_types = list({a["alarm_type"] for a in incident.get("alarms",[])})
    query = f"{ft} {' '.join(alarm_types)} {top_candidates[0]['candidate'].get('node','') if top_candidates else ''}"
    docs = retrieve(query, top_k=2)
    prompt = _build_prompt(incident, top_candidates, docs)
    raw = _call_openai(prompt) if use_openai else None
    if raw is None:
        raw = _rule_based(incident, top_candidates, docs)
    obj, err = _validate(raw, docs)
    if err:
        obj = {"action":"escalate","target":"unknown","explanation":f"Parse error ({err}); escalating [D1]."}
    obj["docs_used"] = [d["doc"] for d in docs]
    obj["doc_scores"] = [d["score"] for d in docs]
    obj["no_procedure"] = (not docs)
    return obj

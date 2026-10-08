"""
app.py — NOC-Pilot Streamlit Dashboard
Run: streamlit run app.py
"""
import streamlit as st
import json, pathlib, random, sys, os, pickle, time
import pandas as pd
import plotly.graph_objects as go
import networkx as nx

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from sim import G, GNB, BACKUP, node_type, subtree, SERVICE_ALARMS
from incidents import generate_incident, FAULT_TYPES
from ranker import rank, train, load_model, build_candidates
from llm import remediate
from gate import process, simulation_check, CONFIDENCE_THRESHOLD
from catalog import CATALOGUE

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NOC-Pilot · 5G Fault Intelligence",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #0b0f1a; color: #e2e8f0; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111827 0%, #0d1424 100%);
    border-right: 1px solid #1e293b;
}

.metric-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
}
.metric-label { font-size: 11px; font-weight: 600; color: #64748b; letter-spacing: 1px; text-transform: uppercase; }
.metric-value { font-size: 28px; font-weight: 700; color: #f1f5f9; margin-top: 4px; }
.metric-sub   { font-size: 12px; color: #94a3b8; margin-top: 2px; }

.alarm-row {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; margin: 3px 0;
    background: #1e293b; border-radius: 8px;
    border-left: 3px solid #ef4444;
    font-family: 'JetBrains Mono', monospace; font-size: 12px;
}
.alarm-row.noise { border-left-color: #374151; opacity: 0.6; }
.alarm-row.ok    { border-left-color: #22c55e; }

.candidate-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 8px; position: relative;
}
.candidate-card.top1 { border-color: #3b82f6; box-shadow: 0 0 0 1px #3b82f633; }

.action-badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
}
.badge-auto   { background: #14532d; color: #4ade80; border: 1px solid #166534; }
.badge-manual { background: #431407; color: #fb923c; border: 1px solid #7c2d12; }
.badge-escalate { background: #1e1b4b; color: #a5b4fc; border: 1px solid #3730a3; }

.sim-ok   { color: #4ade80; font-weight: 600; }
.sim-fail { color: #f87171; font-weight: 600; }

.audit-row {
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    padding: 6px 10px; background: #0f172a; border-radius: 6px;
    border-left: 3px solid #334155; margin-bottom: 4px; color: #94a3b8;
}

.section-header {
    font-size: 13px; font-weight: 600; color: #64748b;
    letter-spacing: 1.5px; text-transform: uppercase;
    border-bottom: 1px solid #1e293b; padding-bottom: 8px; margin: 20px 0 12px;
}

div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white; border: none; border-radius: 8px;
    font-weight: 600; transition: all 0.2s;
}
div[data-testid="stButton"] > button:hover { transform: translateY(-1px); box-shadow: 0 4px 15px #3b82f640; }

.approve-btn > button {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
    font-size: 16px !important; padding: 12px 24px !important;
}
.reject-btn > button {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
}
</style>
""", unsafe_allow_html=True)

# ── State helpers ─────────────────────────────────────────────────────────────
def get_model():
    if "model" not in st.session_state:
        m = load_model()
        if m is None:
            with st.spinner("🔧 Training ranker on 400 synthetic incidents…"):
                from incidents import generate_batch
                m = train(generate_batch(n=400, seed=99))
        st.session_state["model"] = m
    return st.session_state["model"]

def new_incident(fault_type=None, seed=None):
    inc = generate_incident(
        fault_type=fault_type,
        seed=seed if seed is not None else random.randint(0, 99999),
        loss_rate=st.session_state.get("loss_rate", 0.20),
    )
    model = get_model()
    ranked = rank(inc["alarms"], inc["change_log"], model)
    rem = remediate(inc, ranked, use_openai=False)
    decision = process(inc, ranked, rem)
    st.session_state.update({
        "incident": inc, "ranked": ranked,
        "remediation": rem, "decision": decision,
        "approved": None,
    })

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📡 NOC-Pilot")
    st.markdown("<div style='font-size:12px;color:#64748b;margin-top:-10px;margin-bottom:20px'>5G Fault Intelligence · MVP</div>", unsafe_allow_html=True)

    st.markdown("### Generate Incident")
    fault_choice = st.selectbox("Fault type", ["random"] + FAULT_TYPES,
                                 format_func=lambda x: x.replace("_"," ").title())
    loss_pct = st.slider("Alarm loss %", 0, 50, 20, 5)
    st.session_state["loss_rate"] = loss_pct / 100

    if st.button("⚡ Generate New Incident", use_container_width=True):
        ft = None if fault_choice == "random" else fault_choice
        new_incident(fault_type=ft)

    st.markdown("---")
    st.markdown("### View")
    page = st.radio("", ["🔍 Live Incident", "📊 Eval Dashboard", "📋 Audit Log"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("<div style='font-size:11px;color:#374151'>NOC-Pilot · Research Prototype<br>Not for production use</div>", unsafe_allow_html=True)

# ── Auto-load first incident ──────────────────────────────────────────────────
if "incident" not in st.session_state:
    new_incident()

inc      = st.session_state["incident"]
ranked   = st.session_state["ranked"]
rem      = st.session_state["remediation"]
decision = st.session_state["decision"]

# ── Color helpers ─────────────────────────────────────────────────────────────
ALARM_COLORS = {
    "UNREACHABLE": "#ef4444", "LINK_DOWN": "#f97316", "POWER_ALARM": "#eab308",
    "HIGH_LOSS": "#a855f7", "NBR_FAIL": "#ec4899",
    "CONGESTION_WARN": "#64748b", "LATENCY_SPIKE": "#64748b", "CPU_HIGH": "#64748b",
}
NODE_COLORS = {"core":"#6366f1","transport":"#3b82f6","gnb":"#10b981","cell":"#64748b"}

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: LIVE INCIDENT
# ══════════════════════════════════════════════════════════════════════════════
if page == "🔍 Live Incident":
    gt   = inc["ground_truth"]
    alms = [a for a in inc["alarms"] if not a.get("is_noise")]
    noise = [a for a in inc["alarms"] if a.get("is_noise")]
    state = {k: list(v) if isinstance(v, set) else v for k, v in inc["state"].items()}

    # ── Header row ────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ft_display = inc["fault_type"].replace("_"," ").title()
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>Fault Type</div>
            <div class='metric-value' style='font-size:20px'>{ft_display}</div>
            <div class='metric-sub'>ID: {inc['incident_id']}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        top_score = ranked[0]["score"] if ranked else 0
        conf_color = "#4ade80" if top_score >= CONFIDENCE_THRESHOLD else "#f87171"
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>Ranker Confidence</div>
            <div class='metric-value' style='color:{conf_color}'>{top_score:.0%}</div>
            <div class='metric-sub'>Top-1 score · threshold {CONFIDENCE_THRESHOLD:.0%}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>Active Alarms</div>
            <div class='metric-value'>{len(alms)}</div>
            <div class='metric-sub'>{len(noise)} noise · {loss_pct}% loss applied</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        action = decision["action"]
        auto   = decision["auto_execute"]
        badge  = "badge-auto" if auto else ("badge-escalate" if action=="escalate" else "badge-manual")
        label  = "AUTO" if auto else "NEEDS APPROVAL"
        st.markdown(f"""<div class='metric-card'>
            <div class='metric-label'>Autonomy Decision</div>
            <div class='metric-value' style='font-size:18px'>{action.replace('_',' ').title()}</div>
            <div class='metric-sub'><span class='action-badge {badge}'>{label}</span></div>
        </div>""", unsafe_allow_html=True)

    # ── Main columns ──────────────────────────────────────────────────────────
    left, right = st.columns([6, 4], gap="large")

    with left:
        # Topology graph
        c_th, c_tb = st.columns([7, 3])
        c_th.markdown("<div class='section-header'>Network Topology</div>", unsafe_allow_html=True)
        animating = c_tb.button("▶ Animate Workflow", use_container_width=True)

        gt_node         = gt.get("node","")
        top_cand_node   = (ranked[0]["candidate"].get("node") or
                           ranked[0]["candidate"].get("gnb","")) if ranked else ""

        # Build plotly topology
        pos = {}
        pos["core"] = (0, 4)
        for ti, tr in enumerate(["tr0","tr1","tr2"]):
            pos[tr] = (ti * 4 - 4, 3)
            gnbs_of_tr = [n for n in GNB if n.startswith(tr+"_")]
            for gi, gnb in enumerate(gnbs_of_tr):
                x = ti * 4 - 4 + gi - 1.5
                pos[gnb] = (x, 2)
                cells = list(G.successors(gnb))
                for ci, cell in enumerate(cells):
                    pos[cell] = (x - 0.4 + ci * 0.4, 1)

        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0,y0 = pos[u]; x1,y1 = pos[v]
            edge_x += [x0,x1,None]; edge_y += [y0,y1,None]

        graph_placeholder = st.empty()

        def render_graph(visible_alms, show_root=True, show_cand=True):
            alarming_nodes  = {a["node"] for a in visible_alms}
            node_x, node_y, node_col, node_size, node_text, node_sym = [], [], [], [], [], []
            for n in G.nodes():
                x, y = pos[n]
                node_x.append(x); node_y.append(y)
                nt = node_type(n)
                base_col = NODE_COLORS[nt]
                sym = "circle"
                sz  = 12
                if n == gt_node and show_root:
                    col = "#ef4444"; sym = "star"; sz = 22
                elif n == top_cand_node and n != gt_node and show_cand:
                    col = "#f97316"; sym = "diamond"; sz = 18
                elif n in alarming_nodes:
                    col = "#eab308"; sz = 14
                else:
                    col = base_col
                node_col.append(col); node_size.append(sz); node_sym.append(sym)
                alarm_list_for_node = [a["alarm_type"] for a in visible_alms if a["node"]==n]
                node_text.append(f"{n}<br>{'<br>'.join(alarm_list_for_node) if alarm_list_for_node else 'OK'}")

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                line=dict(width=0.8, color="#1e293b"), hoverinfo="none"))
            fig.add_trace(go.Scatter(x=node_x, y=node_y, mode="markers+text",
                marker=dict(size=node_size, color=node_col, symbol=node_sym,
                            line=dict(width=1.5, color="#0b0f1a")),
                text=[n.split("_")[-1] if "_" in n else n for n in G.nodes()],
                textposition="top center",
                textfont=dict(size=8, color="#94a3b8"),
                hovertext=node_text, hoverinfo="text"))

            fig.update_layout(
                showlegend=False, paper_bgcolor="#0b0f1a", plot_bgcolor="#0b0f1a",
                margin=dict(l=0,r=0,t=0,b=0), height=340,
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            )
            graph_placeholder.plotly_chart(fig, use_container_width=True)

        if animating:
            # 1. Clean state
            render_graph([], show_root=False, show_cand=False)
            time.sleep(1.0)
            # 2. Show root cause fault occurring
            render_graph([], show_root=True, show_cand=False)
            time.sleep(1.0)
            # 3. Alarms propagate
            sorted_alms = sorted(alms, key=lambda x: x["timestamp"])
            visible = []
            for a in sorted_alms:
                visible.append(a)
                render_graph(visible, show_root=True, show_cand=False)
                time.sleep(0.3)
            time.sleep(0.5)

        # Final state
        render_graph(alms, show_root=True, show_cand=True)

        # Legend
        st.markdown("""<div style='display:flex;gap:16px;font-size:11px;color:#64748b;margin-top:-10px'>
            <span>🔴 Root cause</span><span>🟠 Top candidate</span>
            <span>🟡 Alarming</span><span>🟢 gNB</span><span>🔵 Transport</span>
        </div>""", unsafe_allow_html=True)

        # Alarms table
        st.markdown("<div class='section-header'>Active Alarms</div>", unsafe_allow_html=True)
        for a in sorted(alms, key=lambda x: x["timestamp"]):
            col = ALARM_COLORS.get(a["alarm_type"],"#64748b")
            st.markdown(f"""<div class='alarm-row'>
                <span style='color:{col};width:130px'>{a['alarm_type']}</span>
                <span style='color:#94a3b8'>{a['node']}</span>
                <span style='color:#475569;margin-left:auto;font-size:10px'>{a['timestamp'][11:19]}</span>
            </div>""", unsafe_allow_html=True)
        if noise:
            st.markdown(f"<div style='font-size:11px;color:#374151;margin-top:6px'>+ {len(noise)} noise alarms filtered</div>", unsafe_allow_html=True)

        # Change log
        if inc["change_log"]:
            st.markdown("<div class='section-header'>Change Log (last 60 min)</div>", unsafe_allow_html=True)
            for ch in inc["change_log"]:
                is_dist = ch.get("is_distractor", False)
                icon = "🔧" if not is_dist else "⚠️"
                st.markdown(f"""<div class='alarm-row' style='border-left-color:{"#3b82f6" if not is_dist else "#374151"}'>
                    <span>{icon}</span>
                    <span style='color:#94a3b8'>{ch.get("type","?")}</span>
                    <span style='color:#64748b'>→ {ch.get("gnb","?")}</span>
                    <span style='color:#475569;margin-left:auto;font-size:10px'>ID:{ch["change_id"]}</span>
                </div>""", unsafe_allow_html=True)

    with right:
        # RCA ranked candidates
        st.markdown("<div class='section-header'>Root-Cause Analysis</div>", unsafe_allow_html=True)
        for i, r in enumerate(ranked[:3]):
            cand = r["candidate"]
            cname = cand.get("node") or cand.get("gnb","?")
            ctype = cand["candidate_type"]
            score = r["score"]
            bar_w = int(score * 100)
            is_top = i == 0
            is_correct = (cname == gt.get("node","") or cand.get("change_id","") == gt.get("change_id",""))
            border = "top1" if is_top else ""
            tick = "✅" if is_correct else ""
            st.markdown(f"""<div class='candidate-card {border}'>
                <div style='display:flex;justify-content:space-between;align-items:center'>
                    <span style='font-weight:600;color:#f1f5f9'>#{i+1} {cname} {tick}</span>
                    <span style='color:#3b82f6;font-weight:700'>{score:.0%}</span>
                </div>
                <div style='font-size:11px;color:#64748b;margin:4px 0'>
                    {("Change: "+cand.get("type","")) if ctype=="change" else ("Node · "+node_type(cname))}
                </div>
                <div style='background:#0f172a;border-radius:4px;height:4px;margin-top:6px'>
                    <div style='width:{bar_w}%;height:4px;background:linear-gradient(90deg,#3b82f6,#6366f1);border-radius:4px'></div>
                </div>
            </div>""", unsafe_allow_html=True)

        # Remediation
        st.markdown("<div class='section-header'>Remediation Plan</div>", unsafe_allow_html=True)
        action = decision["action"]
        target = decision["target"]
        expl   = decision.get("explanation","")
        sim_ok = decision["sim_ok"]
        docs_used = decision.get("docs_used",[])
        auto   = decision["auto_execute"]

        action_info = CATALOGUE.get(action, {})
        risk = action_info.get("risk","?")
        risk_col = {"none":"#4ade80","low":"#4ade80","medium":"#f97316","high":"#ef4444"}.get(risk,"#64748b")

        st.markdown(f"""<div class='candidate-card top1'>
            <div style='font-size:16px;font-weight:700;color:#f1f5f9;margin-bottom:8px'>
                🎯 {action.replace('_',' ').title()}
            </div>
            <div style='font-size:12px;color:#94a3b8'>Target: <span style='color:#f1f5f9'>{target}</span></div>
            <div style='font-size:12px;color:#94a3b8;margin-top:4px'>Risk: <span style='color:{risk_col}'>{risk.upper()}</span></div>
            <div style='font-size:12px;color:#94a3b8;margin-top:8px;line-height:1.6'>{expl}</div>
            <div style='margin-top:10px'>
                <span class='action-badge {"badge-auto" if sim_ok else "badge-escalate"}'>
                    {"✓ SIM PASS" if sim_ok else "✗ SIM FAIL"}
                </span>
            </div>
        </div>""", unsafe_allow_html=True)

        if docs_used:
            st.markdown(f"<div style='font-size:11px;color:#475569'>📄 Runbooks: {', '.join(docs_used)}</div>", unsafe_allow_html=True)

        # Approve / Reject
        st.markdown("<div class='section-header'>Human Approval</div>", unsafe_allow_html=True)
        if not auto:
            st.info(f"⚠️ Requires approval: {'; '.join(decision.get('reasons',['manual action']))}")
        else:
            st.success("✅ Eligible for auto-execution (reversible config + sim pass + confidence ≥ threshold)")

        if st.session_state.get("approved") is None:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown('<div class="approve-btn">', unsafe_allow_html=True)
                if st.button("✅ Approve", use_container_width=True):
                    st.session_state["approved"] = True
                st.markdown('</div>', unsafe_allow_html=True)
            with col_b:
                st.markdown('<div class="reject-btn">', unsafe_allow_html=True)
                if st.button("❌ Reject", use_container_width=True):
                    st.session_state["approved"] = False
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            if st.session_state["approved"]:
                st.success(f"✅ Action APPROVED — `{action}` on `{target}` dispatched to execution engine")
            else:
                st.error("❌ Action REJECTED — incident escalated to senior NOC engineer")

        # Ground truth (for demo)
        with st.expander("🔬 Ground Truth (demo only)"):
            st.json(gt)
            correct = decision["action"] == gt.get("action","")
            if correct: st.success("✅ Action matches ground truth")
            else: st.error(f"❌ Action mismatch · expected: {gt.get('action','?')}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: EVAL DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Eval Dashboard":
    st.markdown("## 📊 Evaluation Dashboard")
    st.info("Runs 100 simulated incidents through the full pipeline. ~10 seconds.")

    if st.button("▶ Run Evaluation", use_container_width=True):
        model = get_model()
        from incidents import generate_batch, generate_incident

        with st.spinner("Running diagnosis evaluation…"):
            incidents = generate_batch(n=100)
            results = {ft: {"top1":0,"top3":0,"total":0,"correct_rem":0} for ft in FAULT_TYPES}
            for inc_e in incidents:
                ft = inc_e["fault_type"]
                gt_e = inc_e["ground_truth"]
                gt_node = gt_e.get("node","")
                gt_cid  = gt_e.get("change_id","")
                gt_action = gt_e.get("action","")
                ranked_e = rank(inc_e["alarms"], inc_e["change_log"], model)
                top_nodes = [r["candidate"].get("node",r["candidate"].get("gnb","")) for r in ranked_e]
                top_cids  = [r["candidate"].get("change_id","") for r in ranked_e]
                hit1 = bool((gt_node in top_nodes[:1]) or (bool(gt_cid) and gt_cid in top_cids[:1]))
                hit3 = bool((gt_node in top_nodes[:3]) or (bool(gt_cid) and gt_cid in top_cids[:3]))
                results[ft]["top1"]  += int(hit1)
                results[ft]["top3"]  += int(hit3)
                results[ft]["total"] += 1
                rem_e = remediate(inc_e, ranked_e)
                results[ft]["correct_rem"] += int(rem_e["action"] == gt_action)

        rows = []
        for ft, r in results.items():
            t = max(r["total"],1)
            rows.append({
                "Fault Type": ft.replace("_"," ").title(),
                "Top-1 (%)": round(r["top1"]/t*100,1),
                "Top-3 (%)": round(r["top3"]/t*100,1),
                "Rem Correct (%)": round(r["correct_rem"]/t*100,1),
                "N": r["total"],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        fig = go.Figure()
        fts = [r["Fault Type"] for r in rows]
        fig.add_bar(name="Top-1 Diagnosis", x=fts, y=[r["Top-1 (%)"] for r in rows],
                    marker_color="#3b82f6")
        fig.add_bar(name="Top-3 Diagnosis", x=fts, y=[r["Top-3 (%)"] for r in rows],
                    marker_color="#6366f1")
        fig.add_bar(name="Remediation Correct", x=fts, y=[r["Rem Correct (%)"] for r in rows],
                    marker_color="#10b981")
        fig.update_layout(barmode="group", paper_bgcolor="#0b0f1a", plot_bgcolor="#0b0f1a",
                          font_color="#94a3b8", legend_bgcolor="#0b0f1a",
                          yaxis=dict(range=[0,105], gridcolor="#1e293b"),
                          xaxis=dict(gridcolor="#1e293b"), height=360,
                          title=dict(text="Diagnosis & Remediation Accuracy by Fault Type",
                                     font=dict(color="#f1f5f9")))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("⚠️ Rule-based mock LLM used (no OpenAI key). Set OPENAI_API_KEY env var for real LLM results.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Audit Log":
    st.markdown("## 📋 Audit Log")
    log_path = pathlib.Path("audit.log")
    if not log_path.exists():
        st.info("No audit entries yet. Generate and approve some incidents first.")
    else:
        entries = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]
        st.markdown(f"**{len(entries)} entries**")
        for e in reversed(entries[-50:]):
            auto_badge = "🟢 AUTO" if e.get("auto_execute") else "🟡 MANUAL"
            sim_badge  = "✓" if e.get("sim_ok") else "✗"
            st.markdown(f"""<div class='audit-row'>
                {e['ts'][11:19]} | {e['fault_type']:<18} | {e['action']:<22} → {e['target']:<15}
                | score:{e['top_score']:.2f} | sim:{sim_badge} | {auto_badge}
            </div>""", unsafe_allow_html=True)
        if st.button("Export as JSON"):
            st.download_button("⬇ Download audit.log", log_path.read_bytes(),
                               "audit.log", "application/json")

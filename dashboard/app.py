"""Streamlit monitoring dashboard: version timeline, accuracy, feedback."""
from __future__ import annotations

import os

import plotly.graph_objects as go
import streamlit as st

try:
    from dashboard.data import load_feedback, load_registry, load_run_history
except ImportError:
    # `streamlit run dashboard/app.py` puts dashboard/ (not the repo root) on
    # sys.path, so the package-qualified import above only works when this
    # module is imported by something that already has the repo root on
    # sys.path (e.g. pytest).
    from data import load_feedback, load_registry, load_run_history

REGISTRY_PATH = os.environ.get("MODEL_REGISTRY_PATH", "models/registry.json")
RUN_HISTORY_PATH = os.environ.get("RUN_HISTORY_PATH", "artifacts/run_history.jsonl")
FEEDBACK_DB_PATH = os.environ.get("FEEDBACK_DB_PATH", "data/feedback/feedback.db")

st.set_page_config(page_title="PhishGuard Dashboard", page_icon="🛡", layout="wide")

st.title("🛡 PhishGuard Dashboard")
st.caption("Model registry, training-run outcomes, and live feedback — refresh anytime.")

if st.button("↻ Refresh"):
    st.rerun()

registry = load_registry(REGISTRY_PATH)
history_df = load_run_history(RUN_HISTORY_PATH)
feedback_df = load_feedback(FEEDBACK_DB_PATH)

models = registry.get("models", [])
live_version = registry.get("live_version")
live_entry = next((m for m in models if m["version"] == live_version), None)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Live version", live_version or "—")
col2.metric("Live accuracy", f"{live_entry['accuracy']:.2%}" if live_entry else "—")
col3.metric("Total predictions", len(feedback_df))
corrections = int((feedback_df["predicted_label"] != feedback_df["correct_label"]).sum()) if not feedback_df.empty else 0
col4.metric("User corrections", corrections)

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("Training runs: accuracy over time")
    if history_df.empty:
        st.info("No training runs recorded yet. Run `python -m ml.train --data ...` to populate this.")
    else:
        fig = go.Figure()
        promoted = history_df[history_df["status"] == "promoted"]
        rejected = history_df[history_df["status"] == "rejected"]
        fig.add_trace(go.Scatter(
            x=history_df["timestamp"], y=history_df["candidate_accuracy"],
            mode="lines", name="candidate accuracy", line=dict(color="#6d8dff", width=1.5),
        ))
        fig.add_trace(go.Scatter(
            x=promoted["timestamp"], y=promoted["candidate_accuracy"],
            mode="markers", name="promoted", marker=dict(color="#34d399", size=11, symbol="circle"),
        ))
        fig.add_trace(go.Scatter(
            x=rejected["timestamp"], y=rejected["candidate_accuracy"],
            mode="markers", name="rejected", marker=dict(color="#f87171", size=11, symbol="x"),
        ))
        fig.update_layout(
            template="plotly_dark", height=380, yaxis_tickformat=".0%",
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Promoted vs rejected")
    if history_df.empty:
        st.info("No runs yet.")
    else:
        counts = history_df["status"].value_counts()
        fig2 = go.Figure(data=[go.Pie(
            labels=counts.index, values=counts.values, hole=0.55,
            marker=dict(colors=["#34d399" if s == "promoted" else "#f87171" for s in counts.index]),
        )])
        fig2.update_layout(template="plotly_dark", height=280, margin=dict(l=10, r=10, t=10, b=10),
                            showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("Model registry")
if models:
    reg_df = pd.DataFrame(models)[["version", "model_type", "accuracy", "n_samples", "trained_at", "promoted"]]
    reg_df["accuracy"] = reg_df["accuracy"].map(lambda a: f"{a:.2%}")
    reg_df["live"] = reg_df["version"] == live_version
    st.dataframe(reg_df.sort_values("trained_at", ascending=False), use_container_width=True, hide_index=True)
else:
    st.info("No promoted models yet.")

st.subheader("Recent feedback")
if not feedback_df.empty:
    show = feedback_df.head(20).copy()
    show["predicted"] = show["predicted_label"].map({0: "safe", 1: "phishing"})
    show["corrected_to"] = show["correct_label"].map({0: "safe", 1: "phishing"})
    show["was_wrong"] = show["predicted_label"] != show["correct_label"]
    st.dataframe(
        show[["created_at", "url", "predicted", "corrected_to", "was_wrong", "model_version"]],
        use_container_width=True, hide_index=True,
    )
else:
    st.info("No predictions logged yet. Use the PhishGuard app to check some URLs.")

"""Streamlit UI. Runs the agent in-process; no separate FastAPI server needed."""
from __future__ import annotations

import json
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from app.graph import get_compiled_agent

st.set_page_config(page_title="NL→SQL Agent", layout="wide")
st.title("Ask your data anything")

with st.sidebar:
    st.markdown("### About")
    st.markdown(
        "Schema-aware NL→SQL with a self-healing validator. "
        "Source: [github.com/.../nl2sql-agent](https://github.com)"
    )
    st.markdown("### Example questions")
    for q in [
        "How many orders were placed in 1995?",
        "Total revenue per region in 1995",
        "Top 5 suppliers by revenue in 1996",
        "Average order value by market segment",
    ]:
        if st.button(q, key=q):
            st.session_state["q"] = q


@st.cache_resource
def agent():
    return get_compiled_agent()


q = st.text_input(
    "Question",
    value=st.session_state.get("q", "What was the total revenue per region in 1995?"),
    key="question",
)

if st.button("Run", type="primary"):
    t0 = time.time()
    with st.spinner("Thinking…"):
        state = agent().invoke({"question": q})
    elapsed = time.time() - t0

    c1, c2 = st.columns([3, 2])

    with c1:
        st.subheader("Result")
        rows = state.get("rows", [])
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            cs = state.get("chart_suggestion") or {}
            if cs.get("type") == "bar":
                st.plotly_chart(px.bar(df, x=cs["x"], y=cs["y"]), use_container_width=True)
            elif cs.get("type") == "line":
                st.plotly_chart(px.line(df, x=cs["x"], y=cs["y"]), use_container_width=True)
        elif state.get("error"):
            st.error(state["error"])
        elif state.get("validation_error"):
            st.error(state["validation_error"])
        else:
            st.info("No rows returned.")

    with c2:
        st.subheader("SQL")
        if state.get("sql"):
            st.code(state["sql"], language="sql")
        if state.get("cube_query"):
            st.subheader("Cube query")
            st.code(json.dumps(state["cube_query"], indent=2), language="json")

        st.caption(
            f"attempts={state.get('attempts', 0)} | "
            f"chart={state.get('chart_suggestion', {}).get('type', '—')} | "
            f"{elapsed:.1f}s"
        )

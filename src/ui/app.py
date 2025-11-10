"""Streamlit UI for interacting with the Strands knowledge graph agent."""

from __future__ import annotations

import streamlit as st

from src.strands.main import create_supervisor_agent


DEFAULT_ASSISTANT_MESSAGE = {
    "role": "assistant",
    "content": (
        "I'm the Knowledge Graph QA agent. Ask about teams, services, "
        "or endpoints and I'll look them up in the ontology."
    ),
}


def _ensure_session_state() -> None:
    """Initialize chat history and agent in session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = [DEFAULT_ASSISTANT_MESSAGE.copy()]
    if "agent" not in st.session_state:
        st.session_state.agent = create_supervisor_agent()


st.set_page_config(
    page_title="Knowledge Graph QA",
    page_icon="???",
    layout="wide",
)

_ensure_session_state()

st.title("Knowledge Graph QA Assistant")
st.caption("Chat with the Strands agent that queries the ontology knowledge graph.")

with st.sidebar:
    st.subheader("Session Controls")
    st.write("Reset the conversation if you want to start fresh.")
    if st.button("Reset chat", type="secondary"):
        st.session_state.messages = [DEFAULT_ASSISTANT_MESSAGE.copy()]
        st.session_state.agent = create_supervisor_agent()
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about teams, services, or endpoints..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Querying knowledge graph..."):
            response_text = ""
            try:
                agent_response = st.session_state.agent(prompt)
                response_text = str(agent_response)
            except Exception as exc:  # pragma: no cover - UI feedback only
                response_text = (
                    "Sorry, something went wrong while contacting the agent. "
                    "Check the Streamlit logs for details."
                )
                st.error(f"Agent error: {exc}")
        st.markdown(response_text)

    st.session_state.messages.append({"role": "assistant", "content": response_text})

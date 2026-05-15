import streamlit as st
from agent import run_agent

st.title("Data and AI Podcast App")

# initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# accept user input
if prompt := st.chat_input("Ask me anything"):
    # display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # run the agent and display the response
    with st.chat_message("assistant"):
        response, tool_calls = run_agent(st.session_state.messages)
        st.markdown(response)

        # show which tools were called, if any
        if tool_calls:
            with st.expander("Sources"):
                for call in tool_calls:
                    st.write(f"**Tool:** {call['name']}")
                    st.write(f"**Args:** {call['args']}")
                    if call["name"] == "list_podcasts":
                        for podcast in call["result"]:
                            st.write(f"- {podcast}")
                    elif call["name"] == "get_episodes":
                        for episode in call["result"]:
                            st.write(f"- {episode['episode_title']} ({episode['published_date']})")
                    elif call["name"] == "semantic_search":
                        for chunk in call["result"]:
                            st.write(f"- {chunk['episode_title']} ({chunk['podcast_name']}): {chunk['chunk_text'][:200]}...")

    st.session_state.messages.append({"role": "assistant", "content": response})
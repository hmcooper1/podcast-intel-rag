import streamlit as st
from openai import OpenAI
from supabase import create_client
from dotenv import load_dotenv
import os

load_dotenv()

st.title("Data and AI Podcast App")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o"

# initalize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# display chat messages from history on app rerun (user: hi)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# accept user input
if prompt := st.chat_input("Ask me anything"):
    # display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # display assistant response in chat message container
    with st.chat_message("assistant"):
        
        # send prompt to gpt-40
        stream = openai_client.chat.completions.create(
            model=st.session_state["openai_model"],
            # send all the past messages from entire conversation to gpt-40
            messages=[
                {"role": "system", "content": """
You are a helpful assistant for a podcast knowledge base.
You have access to transcripts from 20+ AI/ML podcasts covering topics like
machine learning, AI engineering, data science, and biotech AI.
Answer questions about podcast content, episodes, guests, and topics.
If you don't have enough information to answer, say so honestly.
"""},
                *[{"role": m["role"], "content": m["content"]}
                  for m in st.session_state.messages],
            ],
            # get entire response at once
            stream=True,
        )
        response = st.write_stream(stream)

    # add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
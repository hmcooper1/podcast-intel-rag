import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from tools import semantic_search, list_podcasts, get_episodes

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
You are a helpful assistant for a podcast knowledge base.
You have access to transcripts from 20+ AI/ML podcasts covering topics like
machine learning, AI engineering, data science, and biotech AI.
Answer questions about podcast content, episodes, guests, and topics.
Always search the transcripts before answering — don't rely on your own knowledge.
If you don't have enough information to answer, say so honestly.
"""

# tool schemaa: tells openai what tools exist and what arguments they take
TOOLS = [
    # semantic search
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": (
                "Search podcast transcripts for content related to a topic or question. "
                "Use this when the user asks about what podcasts have discussed, "
                "specific topics, guests, or concepts."
            ),
            # function's input arguments (must return query, if no match_count defaults to 5)
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic or question to search for in podcast transcripts",
                    },
                    "match_count": {
                        "type": "integer",
                        "description": "Number of transcript chunks to retrieve. Default 5, max 10.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    # return all podcast names available in database
    {
        "type": "function",
        "function": {
            "name": "list_podcasts",
            "description": "Return all podcast names available in the database. Use this when the user asks what podcasts are available.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # return episodes from a specific podcast
    {
        "type": "function",
        "function": {
            "name": "get_episodes",
            "description": "Return recent episodes from a specific podcast. Use this when the user asks about episodes from a named podcast.",
            "parameters": {
                "type": "object",
                "properties": {
                    "podcast_name": {
                        "type": "string",
                        "description": "The name of the podcast to look up episodes for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of episodes to return. Default 5.",
                    },
                },
                "required": ["podcast_name"],
            },
        },
    },
]

# maps tool name -> actual python function defined in tools.py
TOOL_MAP = {
    "semantic_search": semantic_search,
    "list_podcasts": list_podcasts,
    "get_episodes": get_episodes,
}

# agent loop
def run_agent(messages: list[dict]) -> tuple[str, list[dict]]:
    """
    Run the agent loop. Sends messages to OpenAI, executes any tool calls,
    and loops until OpenAI returns a final text response.

    Returns:
        response:   the final text answer from the model
        tool_calls: list of tool calls made (name, args, result) for display in the UI
    """
    # system prompt + messages (list of dicts showing conversation between user and gpt)
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    tool_calls_log = []

    while True:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            # full messages contain any chunks resulting from tool calling
            messages=full_messages,
            tools=TOOLS,
            tool_choice="auto",  # model decides whether to call a tool
        )

        message = response.choices[0].message

        # no tool call means the model is done — return its text response
        if not message.tool_calls:
            return message.content, tool_calls_log

        # model wants to call one or more tools — add its message to the conversation in dict format
        full_messages.append(message.model_dump(exclude_unset=True))

        for tool_call in message.tool_calls:
            # get func name and arguments from gpt json response
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            # execute and log the tool
            result = TOOL_MAP[name](**args)
            tool_calls_log.append({"name": name, "args": args, "result": result})

            # add the tool result to the conversation so the model can use it
            full_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

        # loop back — model will now read the tool results and either call another tool
        # or return a final text response
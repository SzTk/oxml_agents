from any_agent import AgentConfig
from any_agent.tools import search_web, visit_webpage
from any_llm.utils.aio import run_async_in_sync

from agent_config import get_agent_args
from streaming_tinyagent import StreamingTinyAgent

SIMPLE_INSTRUCTION = "Use the tools, please."

BETTER_INSTRUCTION = """\
You are a web research assistant with access to web search and a browser.

Always use tools to retrieve current information — never answer from memory or prior knowledge.

Follow this sequence:
1. Call search_web with a relevant query to find web pages
2. Call visit_webpage on the most relevant URLs from the search results
3. Report only what you actually retrieved from the web

If the first search doesn't provide enough information, try a different query.\
"""

model_id, api_base, api_key, prompt = get_agent_args(
    "Which are the most used agentic frameworks? Do at most one web search"
)


async def main():
    agent = StreamingTinyAgent(
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=BETTER_INSTRUCTION,
            tools=[search_web, visit_webpage],
        )
    )
    await agent._load_agent()
    result = await agent.run_stream_async(prompt)
    print(f"\n\nFinal: {result}")


run_async_in_sync(main())

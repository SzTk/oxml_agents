import asyncio
import os

from any_agent import AgentConfig
from any_agent.config import MCPStdio

from agent_config import get_agent_args
from streaming_tinyagent import StreamingTinyAgent

SIMPLE_INSTRUCTION = "You must use the available tools to find an answer."

BETTER_INSTRUCTION = """\
You are a Joplin notes assistant with live access to the user's Joplin database via tools.

Always use tools to retrieve real data — never answer from memory or prior knowledge.

When asked about notes, follow this sequence:
1. Call list_notebooks to discover available notebooks
2. Call find_notes_in_notebook (for a specific notebook) or find_notes (for a broad search) to list notes
3. Call get_note if note content is requested
4. Report only what the tools actually returned

If a tool call returns an error or empty result, try an alternative tool or broader query rather than giving up.\
"""

model_id, api_base, api_key, prompt = get_agent_args("""
Look into my Joplin notes and tell me what notes I have.
""")


async def main():
    agent = StreamingTinyAgent(
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=BETTER_INSTRUCTION,
            tools=[
                MCPStdio(
                    command="uv",
                    args=[
                        "--directory",
                        "/home/taka/Documents/github/joplin-mcp",
                        "run",
                        "joplin-mcp",
                    ],
                    env={"JOPLIN_TOKEN": os.environ["JOPLIN_TOKEN"]},
                )
            ],
        )
    )
    await agent._load_agent()
    async with agent:
        result = await agent.run_stream_async(prompt)
    print(f"\n\nFinal: {result}")


asyncio.run(main())

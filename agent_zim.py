from any_agent import AgentConfig, AnyAgent
from any_agent.config import MCPStdio

from agent_config import get_agent_args

SIMPLE_INSTRUCTION = "You must use the available tools to find an answer."

BETTER_INSTRUCTION = """\
You are a knowledge base assistant with access to a ZIM archive via tools.

Always use tools to look up information — never answer from memory or prior knowledge.

When asked a question:
1. Use the available search tools to find relevant entries in the ZIM archive
2. Read the content of the most relevant entries
3. Report only what you actually found in the archive

If the first search returns no results, try alternative or broader search terms.\
"""

model_id, api_base, api_key, prompt = get_agent_args("When was Denny Vrandecic born?")

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions=BETTER_INSTRUCTION,
        tools=[
            MCPStdio(
                command="uvx",
                args=[
                    "zim-mcp-server",
                    "/Users/mala/Downloads/zim"
                ],
            )
        ],
    ),
)

agent_trace = agent.run(prompt)

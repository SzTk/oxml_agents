from any_agent import AgentConfig, AnyAgent
from any_agent.config import MCPStdio

from agent_config import get_agent_args

model_id, api_base, api_key, prompt = get_agent_args("""
Look into my Joplin notes and tell me what notes I have.
""")

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions="""You must use the available tools to find an answer.""",
        tools=[
            MCPStdio(
                command="uv",
                args=[
                    "--directory",
                    "/home/taka/joplin-mcp",
                    "run",
                    "joplin-mcp",
                ],
            )
        ],
    ),
)

agent_trace = agent.run(prompt)
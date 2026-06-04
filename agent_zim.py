from any_agent import AgentConfig, AnyAgent
from any_agent.config import MCPStdio

from agent_config import get_agent_args

model_id, api_base, api_key, prompt = get_agent_args("When was Denny Vrandecic born?")

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions="""You must use the available tools to find an answer.""",
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

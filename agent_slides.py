from any_agent import AgentConfig, AnyAgent
from any_agent.tools import search_web, visit_webpage

from agent_config import get_agent_args

model_id, api_base, api_key, prompt = get_agent_args(
    "Which are the most used agentic frameworks? Do at most one web search"
)

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions="""Use the tools, please.""",
        tools=[search_web, visit_webpage],
    ),
)

agent_trace = agent.run(prompt)

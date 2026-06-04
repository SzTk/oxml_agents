import re
import requests

from any_agent import AgentConfig, AnyAgent
from markdownify import markdownify
from requests.exceptions import RequestException

from agent_config import get_agent_args

def visit_webpage(url: str, timeout: int = 30) -> str:
    """Visits a webpage at the given url and returns its content as a markdown string. Use this to browse webpages.

    Args:
        url: The url of the webpage to visit.
        timeout: The timeout in seconds for the request.
    """
    headers = None
    try:
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()

        markdown_content = markdownify(response.text).strip()

        markdown_content = re.sub(r"\\n{2,}", "\\n", markdown_content)

        return str(markdown_content)

    except RequestException as e:
        return f"Error fetching the webpage: {e!s}"
    except Exception as e:
        return f"An unexpected error occurred: {e!s}"


model_id, api_base, api_key, prompt = get_agent_args("""
What is the post at https://aittalam.github.io/posts/2025-06-17-vibe-reversing/ about?
""")

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions="""You must use the available tools to find an answer.""",
        tools=[visit_webpage],
    ),
)

agent_trace = agent.run(prompt)

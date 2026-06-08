import re
import requests

from any_agent import AgentConfig
from any_llm.utils.aio import run_async_in_sync
from markdownify import markdownify
from requests.exceptions import RequestException

from agent_config import get_agent_args
from streaming_tinyagent import StreamingTinyAgent


def visit_webpage(url: str, timeout: int = 30) -> str:
    """Visits a webpage at the given url and returns its content as a markdown string. Use this to browse webpages.

    Args:
        url: The url of the webpage to visit.
        timeout: The timeout in seconds for the request.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        markdown_content = markdownify(response.text).strip()
        markdown_content = re.sub(r"\\n{2,}", "\\n", markdown_content)
        return str(markdown_content)
    except RequestException as e:
        return f"Error fetching the webpage: {e!s}"
    except Exception as e:
        return f"An unexpected error occurred: {e!s}"


SIMPLE_INSTRUCTION = "You must use the available tools to find an answer."

BETTER_INSTRUCTION = """\
You are a web page reader. You have access to a tool that fetches and converts web pages to text.

Always use tools to retrieve content — never answer from memory.

When asked about a web page:
1. Call visit_webpage with the provided URL
2. Read and summarize the actual content returned by the tool
3. Report only what the tool returned

If the page fails to load, report the error clearly rather than guessing the content.\
"""

model_id, api_base, api_key, prompt = get_agent_args("""
What is the post at https://aittalam.github.io/posts/2025-06-17-vibe-reversing/ about?
""")


async def main():
    agent = StreamingTinyAgent(
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=BETTER_INSTRUCTION,
            tools=[visit_webpage],
        )
    )
    await agent._load_agent()
    result = await agent.run_stream_async(prompt)
    print(f"\n\nFinal: {result}")


run_async_in_sync(main())

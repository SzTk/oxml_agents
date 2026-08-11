import json
import os
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


def search(
    query: str,
    max_results: int = 10,
    time_range: str = "",
    safesearch: str = "moderate",
) -> str:
    """
    Search the web using the Brave Search API.

    Args:
        query: The search query (required)
        max_results: Maximum number of results to return (capped at 20) - default: 10
        time_range: Freshness filter (pd, pw, pm, py for past day/week/month/year) - optional
        safesearch: Safe search level (off, moderate, strict) - default: moderate
    """
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        raise Exception(
            "BRAVE_API_KEY environment variable is not set. "
            "Get a free API key at https://brave.com/search/api/ and set it in .env."
        )

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": query,
        "count": min(max_results, 20),
        "safesearch": safesearch,
    }
    if time_range:
        params["freshness"] = time_range

    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        formatted_results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            }
            for item in data.get("web", {}).get("results", [])
        ]

        summary = {
            "query": query,
            "number_of_results": len(formatted_results),
            "results": formatted_results,
        }
        return json.dumps(summary, indent=2)

    except Exception as e:
        raise Exception(f"Error performing search: {e}")


SIMPLE_INSTRUCTION = "You must use the available tools to find an answer."

BETTER_INSTRUCTION = """\
You are a web research assistant with access to a Brave search engine and a web browser.

Always use tools to retrieve current information — never answer from memory or prior knowledge.

Follow this sequence:
1. Call search with a relevant query to find web pages
2. Call visit_webpage on the most relevant URLs from the search results
3. Report only what you actually retrieved from the web

If the first search doesn't provide enough information, refine the query and search again.\
"""

model_id, api_base, api_key, prompt = get_agent_args("""
Who are the speakers for OxML 2026 MLx Cases?
""")

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions=BETTER_INSTRUCTION,
        tools=[search, visit_webpage],
    ),
)

agent_trace = agent.run(prompt)

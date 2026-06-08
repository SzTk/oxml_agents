import asyncio
import httpx
import json
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


def search(
    query: str,
    format: str = "json",
    categories: str = "",
    engines: str = "",
    language: str = "en",
    pageno: int = 1,
    time_range: str = "",
    safesearch: int = 1,
) -> str:
    """Search the web using SearXNG.

    Args:
        query: The search query (required)
        format: Output format (json, csv, rss) - default: json
        categories: Comma separated list of search categories (optional)
        engines: Comma separated list of search engines (optional)
        language: Language code - default: en
        pageno: Search page number - default: 1
        time_range: Time range (day, month, year) - optional
        safesearch: Safe search level (0, 1, 2) - default: 1
    """
    search_url = "http://localhost:8888/search"
    params = {
        "q": query,
        "format": format,
        "language": language,
        "pageno": pageno,
        "safesearch": safesearch,
    }
    if categories:
        params["categories"] = categories
    if engines:
        params["engines"] = engines
    if time_range:
        params["time_range"] = time_range

    try:
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            response = client.post(search_url, data=params)
            response.raise_for_status()
            if format == "json":
                result = response.json()
                if "results" in result:
                    formatted_results = [
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", ""),
                            "engine": item.get("engine", ""),
                        }
                        for item in result["results"][:10]
                    ]
                    return json.dumps(
                        {"query": query, "number_of_results": len(result.get("results", [])), "results": formatted_results},
                        indent=2,
                    )
                return json.dumps(result, indent=2)
            return response.text
    except Exception as e:
        raise Exception(f"Error performing search: {e}")


SIMPLE_INSTRUCTION = "You must use the available tools to find an answer."

BETTER_INSTRUCTION = """\
You are a web research assistant with access to a SearXNG search engine and a web browser.

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


async def main():
    agent = StreamingTinyAgent(
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=BETTER_INSTRUCTION,
            tools=[search, visit_webpage],
        )
    )
    await agent._load_agent()
    result = await agent.run_stream_async(prompt)
    print(f"\n\nFinal: {result}")


run_async_in_sync(main())

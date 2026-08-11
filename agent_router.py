import json
import re
from pathlib import Path

import httpx
import requests
from any_agent import AgentConfig, AnyAgent
from markdownify import markdownify
from requests.exceptions import RequestException

from agent_config import get_agent_args


def scan_current_dir(pattern: str) -> list[str]:
    """Scans the current directory for files satisfying the provided pattern.

    Args:
        pattern: The pattern used to filter files in the current directory (e.g. "*.txt"
        for text files, "*.py" for python files, "*.*" for all files)

    Returns:
        A string representing the list of filenames that satisfy the provided pattern
    """
    current_dir = Path(".")
    files_list = [str(f) for f in current_dir.glob(pattern)]
    return str(files_list)


def read_file(file_name: str) -> str:
    """Read the contents of the given `file_name`.

    Args:
        file_name: The path to the file you want to read.

    Returns:
        The contents of `file_name`.

    Raises:
        ValueError: For the following cases:
            - If the path to the file is not allowed.
    """
    file_path = Path(file_name)
    return file_path.read_text()


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


ROUTER_INSTRUCTIONS = """\
You are a routing assistant. Classify the user's request into exactly one category
based on what kind of information retrieval it needs:
- "files": the answer is likely found in a local file in the current directory
- "webpage": the user provided a specific URL to fetch and summarize
- "search": the user needs current information found via web search (no specific URL given)

Respond with exactly one of: files, webpage, search.
Lowercase only, no punctuation, no explanation.\
"""

FILES_INSTRUCTIONS = """\
You are a file-reading assistant. The answer is in a file in the current directory.

Always use tools to retrieve data — never answer from memory.

Follow this sequence:
1. Call scan_current_dir with a pattern like "*.csv" to find data files
2. Call read_file on the relevant file to read its contents
3. Extract and report the answer from the file contents

If no matching file is found, try broader patterns such as "*.txt" or "*.*".\
"""

WEBPAGE_INSTRUCTIONS = """\
You are a web page reader. You have access to a tool that fetches and converts web pages to text.

Always use tools to retrieve content — never answer from memory.

When asked about a web page:
1. Call visit_webpage with the provided URL
2. Read and summarize the actual content returned by the tool
3. Report only what the tool returned

If the page fails to load, report the error clearly rather than guessing the content.\
"""

SEARCH_INSTRUCTIONS = """\
You are a web research assistant with access to a SearXNG search engine and a web browser.

Always use tools to retrieve current information — never answer from memory or prior knowledge.

Follow this sequence:
1. Call search with a relevant query to find web pages
2. Call visit_webpage on the most relevant URLs from the search results
3. Report only what you actually retrieved from the web

If the first search doesn't provide enough information, refine the query and search again.\
"""

model_id, api_base, api_key, prompt = get_agent_args("When was Davide Eynard born?")


def _build_agent(instructions: str, tools: list) -> AnyAgent:
    return AnyAgent.create(
        "tinyagent",
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=instructions,
            tools=tools,
        ),
    )


router_agent = _build_agent(ROUTER_INSTRUCTIONS, [])
files_agent = _build_agent(FILES_INSTRUCTIONS, [scan_current_dir, read_file])
webpage_agent = _build_agent(WEBPAGE_INSTRUCTIONS, [visit_webpage])
search_agent = _build_agent(SEARCH_INSTRUCTIONS, [search, visit_webpage])


def route_query(user_input: str) -> str:
    router_trace = router_agent.run(user_input)
    category = router_trace.final_output.strip().lower()
    print(f"[router] category: {category}")

    match category:
        case "files":
            agent = files_agent
        case "webpage":
            agent = webpage_agent
        case "search":
            agent = search_agent
        case _:
            print(f"[router] unrecognized category '{category}', falling back to search")
            agent = search_agent

    trace = agent.run(user_input)
    return trace.final_output


result = route_query(prompt)
print(result)

# DuckDuckGo Search Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `agent_duckduckgo.py`, a standalone web-research agent that uses the `ddgs` library instead of SearXNG for web search, so it can be tried as a lighter-weight alternative without touching the existing SearXNG-based agents.

**Architecture:** Copy the structure of `agent_searxng.py` (a `search()` tool function + a `visit_webpage()` tool function + a `tinyagent` `AnyAgent` wired with both tools). Replace only the body of `search()` with a call to `ddgs.DDGS().text()`, mapping its `title`/`href`/`body` result keys onto the same `title`/`url`/`snippet` output shape the SearXNG version produces. Everything else (`visit_webpage`, agent wiring, prompt) is copied unchanged.

**Tech Stack:** Python 3.13, `ddgs>=9.14.4` (already a dependency), `any-agent` (`tinyagent` backend), `markdownify`, `requests`.

This repo has no automated test suite — verification is done by running the agent script directly (`uv run agent_duckduckgo.py`) and inspecting the output, matching how `agent_searxng.py` is verified.

---

### Task 1: Remove the unused `duckduckgo-search` dependency

**Files:**
- Modify: `pyproject.toml`

Only `ddgs` will be used going forward (see design doc `docs/superpowers/specs/2026-08-11-duckduckgo-search-agent-design.md`). The old `duckduckgo-search` package name was superseded by `ddgs` and is unused anywhere in this repo, so drop it to avoid confusion.

- [ ] **Step 1: Edit `pyproject.toml`**

Current `dependencies` block:

```toml
dependencies = [
    "any-agent[all]",
    "any-llm-sdk[all]",
    "mcpd",
    "markdownify",
    "openai<2.0",
    "ddgs>=9.14.4",
    "duckduckgo-search>=8.1.1",
]
```

Change to:

```toml
dependencies = [
    "any-agent[all]",
    "any-llm-sdk[all]",
    "mcpd",
    "markdownify",
    "openai<2.0",
    "ddgs>=9.14.4",
]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync`
Expected: completes without error; `duckduckgo-search` is removed from the resolved environment, `ddgs` remains.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Remove unused duckduckgo-search dependency, keep ddgs"
```

---

### Task 2: Create `agent_duckduckgo.py`

**Files:**
- Create: `agent_duckduckgo.py`
- Reference: `agent_searxng.py` (structure being copied)

- [ ] **Step 1: Write `agent_duckduckgo.py`**

```python
import json
import re

import requests
from any_agent import AgentConfig, AnyAgent
from ddgs import DDGS
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
    Search the web using DuckDuckGo.

    Args:
        query: The search query (required)
        max_results: Maximum number of results to return - default: 10
        time_range: Time range (d, w, m, y for day/week/month/year) - optional
        safesearch: Safe search level (on, moderate, off) - default: moderate
    """
    try:
        results = DDGS().text(
            query,
            max_results=max_results,
            timelimit=time_range or None,
            safesearch=safesearch,
        )

        formatted_results = [
            {
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
            }
            for item in results
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
You are a web research assistant with access to a DuckDuckGo search engine and a web browser.

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
```

- [ ] **Step 2: Sanity-check the `search()` function in isolation**

Run: `uv run python3 -c "from agent_duckduckgo import search; print(search('OxML 2026 MLx Cases', max_results=3))" `

Expected: valid JSON printed to stdout with `query`, `number_of_results`, and a `results` list of up to 3 objects, each with non-empty `title` and `url` fields. (This import will also trigger the full agent run at module scope — that's expected and covered in Step 3; this step is really about confirming `search()` itself returns well-formed JSON, visible in stdout before the agent's own output.)

- [ ] **Step 3: Run the full agent end-to-end**

Run: `uv run agent_duckduckgo.py`
Expected: no unhandled exceptions; the script prints the agent's tool calls / trace and a final answer that references actual DuckDuckGo search results (not a memory-based answer). Compare qualitatively against `uv run agent_searxng.py` (or the example transcript in `examples/agent_searxng.md`) to confirm DuckDuckGo is returning usable results where SearXNG was failing.

- [ ] **Step 4: Commit**

```bash
git add agent_duckduckgo.py
git commit -m "Add agent_duckduckgo.py as a ddgs-based alternative to SearXNG"
```

---

### Task 3: Document the new agent in README

**Files:**
- Modify: `README.md:16` (agent table)

The README has a table listing each agent file, its tools, and purpose (see the `agent_searxng.py` row at `README.md:16`). Add a row for the new agent so it's discoverable.

- [ ] **Step 1: Read the current table row for context**

`README.md:16`:
```
| `agent_searxng.py` | `search` (SearXNG), `visit_webpage` | セルフホスト検索エンジン SearXNG を使って OxML 2026 のスピーカー情報を調べる |
```

- [ ] **Step 2: Add a new row directly below it**

```
| `agent_duckduckgo.py` | `search` (DuckDuckGo/ddgs), `visit_webpage` | DuckDuckGo（ddgs）を使って OxML 2026 のスピーカー情報を調べる。SearXNGがブロックされやすい問題への軽量な代替として試作 |
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document agent_duckduckgo.py in README"
```

---

## Self-Review Notes

- **Spec coverage:** design doc's "スコープ" (new file only, no stream/router changes, existing SearXNG files untouched) → Task 2 only touches `agent_duckduckgo.py`. "search() のシグネチャ" and "データフロー" → implemented verbatim in Task 2 Step 1. "エラーハンドリング" → `except Exception as e: raise Exception(...)` matches. "instructions文言" → `BETTER_INSTRUCTION` updated. "依存関係" (drop `duckduckgo-search`) → Task 1. "テスト" (manual run) → Task 2 Steps 2-3.
- **No placeholders:** all code blocks are complete, copy-pasteable files/diffs.
- **Type/name consistency:** `search()` signature (`query`, `max_results`, `time_range`, `safesearch`) is identical between the design doc and Task 2's implementation; output keys (`title`, `url`, `snippet`, `query`, `number_of_results`, `results`) match across the module and the sanity-check step.

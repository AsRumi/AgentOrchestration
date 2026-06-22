"""
Tools available to agents.

A "tool" in LangGraph/LangChain is a Python function the agent can call
to interact with the outside world — searching the web, reading files,
calling APIs, etc.

Currently implemented:
  - web_search: DuckDuckGo search (free, no API key required)
  - fetch_url: Retrieve page content from a URL

To add a new tool, define a function decorated with @tool and add it
to the RESEARCHER_TOOLS list.
"""
from langchain_core.tools import tool
from duckduckgo_search import DDGS
import httpx
import re


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return a formatted summary of results.

    Args:
        query: The search query string
        max_results: Number of results to return (default 5)

    Returns:
        Formatted string with titles, URLs, and snippets
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for: {query}"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('href', 'No URL')}\n"
                f"    {r.get('body', 'No description')}"
            )

        return "\n\n".join(formatted)

    except Exception as e:
        return f"Search failed: {str(e)}"


@tool
def fetch_url(url: str) -> str:
    """
    Fetch the text content of a webpage.

    Args:
        url: The URL to fetch

    Returns:
        Cleaned text content of the page (first 3000 chars)
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ConductorBot/1.0)"}
        response = httpx.get(url, headers=headers, timeout=10, follow_redirects=True)
        response.raise_for_status()

        # Basic HTML stripping
        text = re.sub(r'<[^>]+>', ' ', response.text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text[:3000] + ("..." if len(text) > 3000 else "")

    except Exception as e:
        return f"Failed to fetch {url}: {str(e)}"


# The tools available to the Researcher agent
RESEARCHER_TOOLS = [web_search, fetch_url]

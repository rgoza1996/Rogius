"""
Web Search Module for Rogius Agents

Provides DuckDuckGo web search capabilities for agents to use when:
- Stuck on errors and need external documentation
- Local environment context is insufficient
- User explicitly requests web search

Free, no API key required.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    """Single web search result."""
    title: str
    url: str
    snippet: str


class WebSearchClient:
    """Client for web search operations using DuckDuckGo."""

    def __init__(self, max_results: int = 5):
        self.max_results = max_results
        self._last_results: list[SearchResult] = []

    async def search(self, query: str, max_results: Optional[int] = None) -> list[SearchResult]:
        """
        Perform a web search using DuckDuckGo.

        Args:
            query: Search query string
            max_results: Maximum number of results (defaults to self.max_results)

        Returns:
            List of SearchResult objects
        """
        max_r = max_results or self.max_results

        try:
            # Try to import duckduckgo-search
            from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_r):
                    results.append(SearchResult(
                        title=r.get("title", "Untitled"),
                        url=r.get("href", ""),
                        snippet=r.get("body", "")
                    ))

            self._last_results = results
            return results

        except ImportError:
            # Fallback if package not installed
            print("[WebSearch] Warning: duckduckgo-search not installed. Install with: pip install duckduckgo-search")
            return []
        except Exception as e:
            print(f"[WebSearch] Error during search: {e}")
            return []

    def format_results_for_llm(self, results: Optional[list[SearchResult]] = None) -> str:
        """
        Format search results as a string for LLM consumption.

        Args:
            results: List of SearchResult (uses last search if None)

        Returns:
            Formatted string with search results
        """
        results = results or self._last_results

        if not results:
            return "No web search results available."

        lines = ["Web Search Results:", "=" * 50]

        for i, r in enumerate(results, 1):
            lines.extend([
                f"\n[{i}] {r.title}",
                f"URL: {r.url}",
                f"Summary: {r.snippet[:300]}{'...' if len(r.snippet) > 300 else ''}"
            ])

        lines.append("\n" + "=" * 50)
        return "\n".join(lines)

    async def search_and_format(self, query: str, max_results: Optional[int] = None) -> str:
        """
        Search and immediately format results for LLM.

        Args:
            query: Search query string
            max_results: Maximum number of results

        Returns:
            Formatted search results string
        """
        results = await self.search(query, max_results)
        return self.format_results_for_llm(results)


# Global instance for easy access
_web_search_client: Optional[WebSearchClient] = None


def get_web_search_client() -> WebSearchClient:
    """Get or create the global web search client instance."""
    global _web_search_client
    if _web_search_client is None:
        _web_search_client = WebSearchClient()
    return _web_search_client


async def web_search(query: str, max_results: int = 5) -> str:
    """
    Convenience function for web search.

    Args:
        query: Search query string
        max_results: Maximum number of results (default 5)

    Returns:
        Formatted search results as string
    """
    client = get_web_search_client()
    return await client.search_and_format(query, max_results)

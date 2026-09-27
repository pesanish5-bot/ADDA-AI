import re
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.providers import ProviderError

TAVILY_URL = 'https://api.tavily.com/search'
MAX_RESULTS = 5
TIMEOUT_SECONDS = 8.0


def _http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return value.strip()
    return None


def _citations(results: list) -> list[dict]:
    citations = []
    for index, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            continue
        url = _http_url(item.get('url'))
        if not url:
            continue
        title = str(item.get('title') or '').strip() or url
        excerpt = str(item.get('content') or '').strip()[:1200]
        citations.append({'id': f's{index}', 'title': title, 'url': url, 'excerpt': excerpt})
        if len(citations) >= MAX_RESULTS:
            break
    return citations


def _answer(query: str, payload: dict, citations: list[dict], snippets: list[str]) -> str:
    def escape(text: str) -> str:
        return re.sub(r'([\\`\[\]()])', r'\\\1', text.replace('\n', ' '))
    if not citations:
        return 'No web sources were returned for this query. Try a more specific search.'
    generated = payload.get('answer')
    lead = generated.strip() if isinstance(generated, str) and generated.strip() else ''
    lines = []
    if lead:
        lines.extend([
            escape(lead),
            '',
            'Tavily summary from retrieved sources. Full pages have not been independently verified.',
            '',
        ])
    else:
        lines.extend([
            f'Search evidence for: {escape(query)}',
            'Retrieved snippets; full pages have not been independently verified.',
            '',
        ])
    for citation, snippet in zip(citations, snippets, strict=True):
        detail = f" — {escape(snippet)}" if snippet else ''
        lines.append(f"- [{citation['id']}] {escape(citation['title'])}{detail}")
    lines.append('')
    lines.append('Citations are the URLs returned by Tavily. No extra sources were added.')
    return '\n'.join(lines)


class SearchProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, query: str) -> dict:
        key = self.settings.tavily_api_key.strip()
        if not key:
            raise ProviderError(
                'Search is not configured. Add TAVILY_API_KEY to services/api/.env '
                '(backend only), then restart the API. Do not put the key in the frontend.',
                'search_not_configured', 503,
            )
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                response = client.post(
                    TAVILY_URL,
                    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                    json={'query': query, 'max_results': MAX_RESULTS, 'include_answer': True,
                          'search_depth': 'basic'},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderError('Web search timed out. Try a shorter query.',
                                'search_timeout', 504) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                raise ProviderError('Tavily rejected the request. Check TAVILY_API_KEY.',
                                    'search_unauthorized', 503) from exc
            if status == 429:
                raise ProviderError('The search provider rate limit was reached. Try again shortly.',
                                    'search_rate_limited', 503) from exc
            raise ProviderError('Web search failed. Try again.', 'search_unavailable', 502) from exc
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ProviderError('Web search failed. Try again.', 'search_unavailable', 502) from exc

        results = payload.get('results') if isinstance(payload, dict) else None
        if not isinstance(results, list):
            results = []
        citations = _citations(results)
        snippets = []
        for item in results:
            if not isinstance(item, dict) or not _http_url(item.get('url')):
                continue
            content = str(item.get('content') or '').strip()
            snippets.append(content[:220] + ('…' if len(content) > 220 else ''))
            if len(snippets) >= len(citations):
                break
        return {
            'answer': _answer(query, payload if isinstance(payload, dict) else {}, citations, snippets),
            'citations': citations,
            'source_count': len(citations),
        }

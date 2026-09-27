"""Two bounded evidence lookups, followed by an honest extractive brief.

This module does not infer conclusions, execute source instructions, or call an
LLM. Web evidence comes only from the configured SearchProvider's snippets.
"""
import re


def plan_research(query: str) -> list[str]:
    topic = ' '.join(query.split())[:1800]
    # Summary trigger words would otherwise make the document retriever return
    # the same representative pages for both checks instead of matching risks.
    focused = re.sub(r'\b(summar(?:y|ize|ise)|overview|main findings|key points)\b',
                     '', topic, flags=re.IGNORECASE)
    focused = ' '.join(focused.split())
    return [topic, f'{focused} evidence limitations risks'.strip()]


def collect_research(query: str, plan: list[str], document_store,
                     document_id: str | None, document_token: str | None,
                     search_provider, owner_id: str = '') -> dict:
    # Clamp independently of the planner: callers cannot request unbounded work.
    questions = plan[:2] or plan_research(query)
    citations, checks, seen = [], [], set()
    for question in questions:
        if document_id:
            result = document_store.answer(
                document_id, document_token or '', question, owner_id=owner_id
            )
        else:
            result = search_provider.search(question)
        evidence_count = 0
        for citation in result.get('citations', []):
            excerpt = citation.get('excerpt')
            if not isinstance(excerpt, str) or not excerpt.strip():
                continue
            evidence_count += 1
            key = ((citation.get('document_id'), citation.get('page'), excerpt)
                   if document_id else (citation.get('url'), excerpt))
            if key in seen:
                continue
            seen.add(key)
            citations.append({**citation, 'id': f'R{len(citations) + 1}'})
        checks.append({'query': question, 'source_count': evidence_count})
    return {'plan': questions, 'citations': citations, 'checks': checks,
            'provider': 'extractive' if document_id else 'tavily'}


def _escape(text: str) -> str:
    return re.sub(r'([\\`*_{}\[\]()<>#+.!|~-])', r'\\\1', text)


def render_research(query: str, collection: dict) -> dict:
    citations = collection['citations']
    document = collection['provider'] == 'extractive'
    blocks = ['## Research evidence brief',
              '**Extractive workflow — no AI synthesis or independent fact-checking.**',
              f'Question: {_escape(query)}',
              '### Checks performed']
    for check in collection['checks']:
        blocks.append(f"- {_escape(check['query'])} — {check['source_count']} matching evidence passages")
    if not citations:
        blocks.append('Insufficient evidence: no source excerpts were returned. '
                      'Try more specific terms. No conclusion can be drawn from this result.')
    else:
        blocks.extend(['### Collected evidence',
                       'Exact retrieved document passages follow; keyword matches are not proof of a claim.'
                       if document else
                       'Search-provider snippets follow; full source pages have not been read or independently verified.'])
        for citation in citations:
            location = f" — Page {citation['page']}" if document else ''
            blocks.append(f"**[{citation['id']}] {_escape(citation['title'])}{location}**\n\n" +
                          '\n'.join(f'> {_escape(line)}' for line in citation['excerpt'].splitlines()))
        blocks.append('### Limits\nThis brief organizes retrieved evidence, rather than generating a conclusion. '
                      'It does not establish completeness, source quality, agreement, or factual accuracy. '
                      'A query for limitations does not prove that all risks have been found.')
    return {'answer': '\n\n'.join(blocks), 'citations': citations,
            'source_count': len(citations), 'provider': collection['provider']}

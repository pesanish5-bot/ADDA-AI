# ADR-0004: Vector store and retrieval

Status: Accepted 2026-09-24. Implementation: Phase 3.

## Context

Document retrieval scores chunks by keyword overlap. It is deterministic and cites pages
but misses paraphrase. Corpus size per user is small (tens of documents, ≤300 chunks each).

## Options

- Separate vector database (Qdrant, OpenSearch Serverless, Pinecone): another service,
  another credential, another failure mode, for a corpus that fits in Postgres.
- `pgvector` in the primary database (ADR-0002) with HNSW index, embeddings from Bedrock
  Titan Text Embeddings v2, hybrid rank with Postgres full-text search.

## Decision

`pgvector` + Postgres full-text (hybrid). Existing keyword scorer stays as the fallback
when embeddings are unavailable and as the baseline in retrieval tests.

## Consequences

- Embedding calls cost money per upload; bounded by existing page/char limits.
- Retrieval quality tests use the sample PDF with known question → page pairs.
- Grounded answers pass only retrieved chunks to the model, framed as untrusted data,
  and must cite chunk ids the API can verify before returning.

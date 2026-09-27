# ADR-0002: Primary database

Status: Accepted 2026-09-24. Implementation: Phase 2.

## Context

No database exists. Needed: users (from the IdP), conversations, messages, documents
(metadata, ownership, expiry), document chunks with embeddings, research jobs, audit
events. Access patterns are relational (list my conversations, messages in order, chunks
for a document ranked by similarity) and need transactions for ownership checks.

## Options

- DynamoDB: serverless and cheap, but similarity search needs a second system and
  relational queries need careful key design that the team would rediscover repeatedly.
- PostgreSQL (RDS or Aurora Serverless v2) with `pgvector`: one system for relational data
  and vectors, SQLAlchemy + Alembic migrations, well understood.

## Decision

PostgreSQL 16 with `pgvector`. Aurora Serverless v2 (min 0.5 ACU) for staging/production;
a local Postgres container in `compose.yaml` for development. SQLAlchemy 2.x, Alembic
migrations committed with code and run as a deploy step before the new task starts.

## Consequences

- Introduces VPC, subnets and Secrets Manager for the DB credential (Phase 2 infra).
- Backups: automated snapshots with 7-day retention, point-in-time recovery on; restore
  drill documented in OPERATIONS.md before production.
- Every table with user data carries `user_id`; all queries filter by it (tested).

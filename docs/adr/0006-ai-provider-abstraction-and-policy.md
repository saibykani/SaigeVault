# ADR-0006: Provider-independent AI layer gated by an AI processing policy

**Status:** Accepted · **Date:** 2026-10-01

## Context

The vault must not be locked into a single AI vendor, and the user must control whether document content may leave their deployment.

## Decision

- `services/ai` (`saige_ai`) defines protocols: `LLMProvider`, `EmbeddingProvider`, `RerankerProvider`, `OCRProvider`. Application code depends only on these. Concrete adapters (Anthropic Claude, OpenAI, Google, Ollama, Tesseract…) are added in later phases and selected via environment variables (`LLM_PROVIDER`, `LLM_MODEL`, …).
- Each provider declares its **locality**: `local` (runs inside the deployment) or `third_party` (content leaves the deployment).
- `AI_PROCESSING_POLICY` (`disabled` | `local_only` | `third_party_allowed`) is enforced by `saige_ai.policy.ensure_allowed()`. Every code path that sends document content to a provider must call it.
- **The default is `disabled`.** Nothing is sent anywhere until the operator opts in.

## Consequences

- Clients read the policy from `GET /api/v1/system/info` and explain it in the UI.
- Pipeline stages skipped by policy are recorded as `skipped_by_policy` (`StageStatus`), never silently dropped.

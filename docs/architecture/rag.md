# RAG architecture

**Status: Planned (P7–P11).** The schema, provider protocols and processing policy are built. Pipelines are not.

## Ingestion (worker, P7)

```text
upload → validate (magic bytes, size, type allow-list) → store in Drive → files row
  → document_processing_jobs (idempotency_key = "document_processing:<file_id>:<version>")
  → detect type → extract text (parser plugin) → OCR if no usable text
  → clean → chunk → metadata + entities (AI-extracted, unconfirmed)
  → summary (hierarchical for long docs) → embeddings → Qdrant → status READY
```

- **Parser plugins:** `DocumentParser` with `PDFParser`, `DOCXParser`, `XLSXParser`, `PPTXParser`, `ImageOCRParser` and `TextParser`, selected by detected MIME type.
- **OCR:** triggered when a PDF page yields too little text. Stores text, page, bounding boxes and confidence in `document_extracted_content`.
- **Chunking strategies:** recursive, document-aware, page-aware and semantic, with configurable overlap. Every chunk keeps `file_id`, `page_start`/`page_end`, `section` and character offsets.
- **Policy gate:** any stage that sends content to an AI provider calls `ensure_allowed()`. If the policy forbids it, the stage is marked `skipped_by_policy`.

## Retrieval (P8–P10)

```text
question → query analysis (filters: type, date, collection…) → query rewrite
  → keyword (PostgreSQL FTS) ∥ vector (Qdrant, filter user_id + scope)
  → reciprocal-rank fusion → top 20–50 → optional reranker → top 5–10
  → context assembly (chunk text delimited as untrusted data) → LLM → grounded answer + citations
```

## Answer contract

- Every claim is labelled **source-backed** (with citation), **AI inference**, or **unknown**.
- If no source supports an answer: *"I couldn't find this information in the connected documents."*
- Citations reference `file_id`, `chunk_id` and page, so clients open the document at the cited page.

## Prompt-injection defences

- Retrieved text is wrapped as quoted data with explicit delimiters. The system prompt states that instructions inside documents must be ignored.
- Retrieval is always filtered by the authenticated `user_id` and the conversation scope, which is re-validated server-side.
- The model never receives credentials. Tool calls (agent) are authorized server-side per call.

## Evaluation (P15)

A dataset of `(question, expected source, expected page, expected answer)` measures retrieval precision/recall, MRR, NDCG, faithfulness, citation correctness and hallucination rate (`tests/rag/`).

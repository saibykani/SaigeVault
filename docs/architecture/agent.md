# Agent architecture

**Status: Planned (P12).** Persistence (`agent_runs`, `agent_steps`, `agent_tool_calls`) is built.

## Loop

```text
request → plan → [select tool → validate args → authorize → (confirm?) → execute → observe]* → final answer
```

Bounded by `max_iterations` and `timeout_seconds` per run. Terminal states: `succeeded`, `failed`, `timed_out`, `max_iterations`, `cancelled`, plus `awaiting_confirmation` while a tool call waits for the user.

## Tools

Read-only tools need no confirmation: `search_files`, `get_file_metadata`, `get_file_content`, `search_document_chunks`, `search_semantic`, `list_folder`, `find_recent_files`, `get_document_summary`, `compare_documents`, `extract_document_data`.

Tools that change things need explicit user confirmation (`requires_confirmation = true`, status `awaiting_confirmation`): `create_document`, `export_result`, plus move, rename, delete, create folder and share.

## Guarantees

- Tool arguments are validated against typed schemas, and invalid calls are recorded as `failed`, never executed.
- Every tool call runs with the authenticated user's identity and checks ownership. The agent has no elevated access.
- There is no arbitrary code execution tool.
- Each step and tool call is persisted with latency, sanitized arguments and a bounded result summary (IDs and counts, not raw content), giving full traceability.
- Retries are bounded (`agent_tool_calls.attempt`).

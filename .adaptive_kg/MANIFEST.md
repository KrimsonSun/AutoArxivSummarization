# Adaptive KG Agent Graph

This directory is an agent-readable export of the code knowledge graph.

- Root: `/Users/yijunsun/Documents/Git/AutoArxivSummarization`
- Nodes: `7455`
- Edges: `16621`
- Schema version: `1`

Read order for coding agents:

1. Open `manifest.json`.
2. Search `nodes.jsonl` by `name`, `path`, `type`, or `external_id`.
3. Follow `edges.jsonl` through `DEFINES`, `IMPORTS`, `CALLS`, and `TYPE_REF`.
4. If you discover a graph update, append a JSON object to
   `pending_updates.jsonl` instead of editing generated files directly.

Generated files are safe to refresh. `pending_updates.jsonl` is intentionally
append-only so human or CI validation can accept/reject proposed memory changes.

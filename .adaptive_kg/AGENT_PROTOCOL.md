# Agent Protocol

This graph is for third-party coding agents such as Claude Code, Codex, Cursor
Agent, or any local/cloud model.

## What to read

- `nodes.jsonl`: one node per line. Important fields: `external_id`, `type`,
  `name`, `path`, `start`, `end`, `description`, `memory`.
- `edges.jsonl`: one edge per line. Important fields: `src_external_id`,
  `dst_external_id`, `type`, `confidence`.

## What not to do

- Do not edit `nodes.jsonl` or `edges.jsonl` directly; they are generated.
- Do not invent graph facts without file/line evidence.
- Do not overwrite history. If a fact changed, propose a new valid interval or
  replacement edge in `pending_updates.jsonl`.

## How to propose updates

Append JSONL records to `pending_updates.jsonl`.

Node update:

```json
{"op":"upsert_node","external_id":"symbol:path.py:Name","type":"Function","name":"Name","path":"path.py","start":10,"end":30,"description":"New description","evidence":"path.py:10-30","confidence":0.9}
```

Edge update:

```json
{"op":"upsert_edge","src_external_id":"symbol:a.py:A","dst_external_id":"symbol:b.py:B","type":"CALLS","evidence":"a.py:42","confidence":0.8}
```

Retire stale edge:

```json
{"op":"retire_edge","src_external_id":"symbol:a.py:A","dst_external_id":"symbol:b.py:B","type":"CALLS","evidence":"commit or file evidence","confidence":0.8}
```

The validating writer should merge only updates with concrete evidence.

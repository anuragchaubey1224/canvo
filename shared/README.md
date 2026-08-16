# Shared contract (client ↔ agent-service)

One source of truth for the messages that cross the wire. Mirror this into:

- **Client (TS):** Zod schemas in `web/src/transport/`
- **Service (Python):** Pydantic models in `agent/app/schema.py`

A contract test should fail CI if the two drift apart (PLAN.md §4).

## Messages

**`AgentInput`** (client → service)

```jsonc
{
  "message": "draw a login flow",
  "session_id": "dev",
  "canvas_context": {
    "focused_shapes": [{ "id": "x", "type": "geo", "x": 0, "y": 0, "w": 160, "h": 80, "text": "Cart" }],
    "blurry_shapes": [],
    "screenshot": null            // base64 PNG; used by the Critic (vision)
  },
  "llm": {                        // optional BYOK override; omit to use server default
    "provider": "openrouter",     // "anthropic" | "openrouter" | "openai-compatible"
    "model": "anthropic/claude-sonnet-4.5",
    "api_key": "sk-or-...",       // used per-request; never logged/persisted
    "base_url": null              // defaults to OpenRouter for non-anthropic providers
  }
}
```

**`AgentAction`** (service → client, streamed one per SSE `data:` line)

```jsonc
{ "type": "create", "shape": { "id": "a", "type": "geo", "x": 100, "y": 100, "w": 160, "h": 80, "text": "Start" } }
{ "type": "update", "shape_id": "a", "shape": { "id": "a", "type": "geo", "x": 120, "y": 100, "w": 200, "h": 80, "text": "Start" } }
{ "type": "delete", "shape_id": "a" }
```

The stream ends with an SSE `event: done` carrying `{ "iterations": N }`.

See `actions.schema.json` for the machine-readable JSON Schema.

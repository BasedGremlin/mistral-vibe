# OKComputer Swarm × MASTERZIP v11 — Integrated Runtime Guide

Version: 1.0.0  
Date: 2026-07-16  
Project: ABCAA-TAGAYTAY-2026 / OKComputer Advanced Swarm AI  
Supabase project: `dxyghtyjndylvfugutsr` (`ap-southeast-1`)

## What changed

The original application looked like a multi-agent system, but its workspace generated hard-coded agent replies and timing claims. The backend only selected agents and inserted rows; it did not call a model or execute a real agent loop.

This build replaces the simulated core with:

1. **OpenAI Agents SDK** as the primary agent runtime.
2. **Supabase private control-plane tables** for states, events, and resumable checkpoints.
3. **Hugging Face Transformers.js local embeddings** for semantic role routing, with remote model loading disabled by default.
4. **Optional Claude critic** through Anthropic's official OpenAI SDK compatibility endpoint.
5. **A strict state machine** that prevents direct jumps from planning to completion.
6. **A real workspace UI** that shows persisted provider output and never invents agent messages.

## Canonical execution path

```text
INTAKE
  → PLAN
  → ROUTE
  → EXECUTE
  → CRITIQUE
  → VALIDATE
  → PERSIST
  → COMPLETE
```

Any active state may transition to `FAILED`. Completion cannot bypass validation.

## Provider responsibilities

### OpenAI

OpenAI is the primary orchestrator. It runs the planner, selected specialists, validator, and synthesizer. The Agents SDK receives two bounded tools:

- `get_project_validation_state`
- `classify_action_gate`

The tools expose project state and classify actions without executing physical, financial, destructive, publication, or sales actions.

### Claude

Claude is secondary and optional. It is not treated as an orchestrator. When `ANTHROPIC_API_KEY` exists, the system sends the draft through Anthropic's official OpenAI SDK compatibility endpoint and asks Claude to act as an adversarial critic.

The route is installed but cannot be live-tested without a Claude API key. A consumer Claude subscription or Google-account authorization is not an API credential.

### Hugging Face

The local semantic router uses:

- Package: `@huggingface/transformers`
- Default model: `mixedbread-ai/mxbai-embed-xsmall-v1`
- Task: `feature-extraction`
- Pooling: mean
- Normalization: enabled

The adapted Hugging Face design deliberately changes the default cloud-first tutorial:

```ts
env.allowRemoteModels = false;
env.localModelPath = HF_LOCAL_MODEL_PATH;
env.cacheDir = HF_CACHE_DIR;
```

This means model files remain local. Supabase receives no weights, tokens, caches, or bulk artifacts.

Recommended local root:

```text
%USERPROFILE%\Desktop\HuggingFaces
```

If Desktop is redirected into OneDrive or another sync service, set `HF_LOCAL_MODEL_PATH` to a non-synced local drive instead.

Expected local model structure:

```text
HuggingFaces/
└── mixedbread-ai/
    └── mxbai-embed-xsmall-v1/
        ├── config.json
        ├── tokenizer.json
        ├── tokenizer_config.json
        └── onnx/
            └── model_quantized.onnx
```

If the local model is absent, the router fails closed and uses deterministic keyword routing. It does not silently download the model unless `HF_ALLOW_REMOTE_MODELS=true` is explicitly set.

### Supabase

Supabase is control-plane-only. The migration creates:

```text
control.swarm_runs
control.swarm_events
control.swarm_checkpoints
```

RLS is enabled and no anon/authenticated policies are created. Writes require a server-side service-role key.

The migration also extends the reviewed dry-run connector outbox targets with:

```text
openai
anthropic
huggingface
canva
```

No connector write becomes automatically approved.

### Canva

Canva is used as the visual documentation and operator-manual surface, not as the source of truth. Generated field manuals, architecture maps, and workflow cards must reference the versioned runtime state. Canva content cannot promote a physical build or claim compliance by itself.

## Setup

Copy `.env.example` to `.env` and populate only server-side secrets.

Required for the current application shell:

```env
APP_ID=
APP_SECRET=
DATABASE_URL=
KIMI_AUTH_URL=
KIMI_OPEN_URL=
```

Required for real OpenAI execution:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.4
OPENAI_SWARM_MAX_WORKERS=3
```

Optional Claude critic:

```env
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-4-6
```

Supabase control plane:

```env
SUPABASE_PROJECT_REF=dxyghtyjndylvfugutsr
SUPABASE_URL=https://dxyghtyjndylvfugutsr.supabase.co
SUPABASE_SERVICE_ROLE_KEY=
```

Local Hugging Face routing:

```env
HF_LOCAL_ROUTER_ENABLED=true
HF_LOCAL_MODEL_PATH=
HF_CACHE_DIR=
HF_EMBEDDING_MODEL=mixedbread-ai/mxbai-embed-xsmall-v1
HF_ALLOW_REMOTE_MODELS=false
```

Never expose `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `SUPABASE_SERVICE_ROLE_KEY` through a `VITE_` variable.

## Commands

```bash
npm install
npm run check
npm test
npm run build
npm run db:push
npm run db:seed
npm run dev
```

## First verification run

Use a bounded request:

```text
Audit MASTERZIP v11. Separate implemented code, placeholders, unsupported claims, and the exact evidence required before VAL-1.
```

Expected behavior:

1. The home screen remains pending while real providers execute.
2. The workspace displays persisted messages rather than animations.
3. OpenAI contributions identify provider and phase.
4. Claude shows `optional` unless a valid API key exists.
5. The Supabase control run contains state events and checksummed checkpoints when the service role is configured.
6. The Hugging Face router either uses the local model or logs a deterministic fallback.
7. The final synthesis preserves blockers and does not claim VAL-1 passed.

## Remaining boundary

The UI and agent catalog still use the legacy MySQL/Drizzle data layer. Supabase is now the durable execution control plane, not yet the full application database. That is intentional for the first integration: it avoids an unsafe full rewrite while establishing a clean migration boundary.

The next database phase should port users, agents, swarms, messages, and tasks to Postgres only after:

- a complete schema mapping,
- auth strategy replacement,
- RLS design,
- migration rehearsal,
- rollback test,
- and parity verification.

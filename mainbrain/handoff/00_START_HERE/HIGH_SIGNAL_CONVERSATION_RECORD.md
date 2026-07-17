# High-Signal Conversation Record

## Original consolidation problem

Two complementary assets were identified:

- MASTERZIP v11: engineering domain knowledge, validation logic, FMEA/compliance concepts, and prototype scripts.
- OKComputer Advanced Swarm: modern React/TypeScript application shell with authentication, database, agent UI, and history.

The chosen strategy was to fuse them through adapters and evidence gates rather than paste engineering scripts into the UI or continue expanding the projects separately.

## Major architectural decisions

### 1. OpenAI is the primary orchestrator

The integrated runtime uses an OpenAI Agents SDK path for planner, specialist workers, validator, and synthesizer. It includes explicit safety instructions, project-state retrieval, and action classification gates.

Status: code present. Live execution still requires a valid `OPENAI_API_KEY` in the server environment. A secure key-setup flow was initiated during the conversation, but no raw key was exposed or added to this package.

### 2. Claude is optional and adversarial

Claude was assigned the critic role rather than primary authority. Its output is routed into OpenAI validation and final synthesis.

Status: adapter present. No direct Claude connector or usable Anthropic API key was available. Gmail showed account/API-related correspondence, which is evidence of an account relationship, not authorization for this application.

### 3. Hugging Face is local-first

Transformers.js was adapted for local semantic routing/embeddings. The selected default model in code is `mixedbread-ai/mxbai-embed-xsmall-v1`. Remote model loading is disabled unless explicitly enabled. Model files are not bundled.

Status: code present; model inference not run in this environment.

### 4. Supabase is metadata control plane, not bulk storage

The live project `dxyghtyjndylvfugutsr` received:

- `control.swarm_runs`
- `control.swarm_events`
- `control.swarm_checkpoints`
- service-role-only RPC bridge functions
- connector target expansion for OpenAI, Anthropic, Hugging Face, and Canva

An RPC smoke test created a temporary run, appended an event, wrote a checkpoint, read it back, and deleted it.

### 5. Canva is documentation surface only

Four operator-guide candidates were generated. Canva is not the source of engineering truth and does not replace code, test evidence, Supabase state, or physical validation records.

Candidate URLs retained from the conversation:

- https://www.canva.com/d/oAgsMvfUHEain3d
- https://www.canva.com/d/NGqy8euQ9P4zRz5
- https://www.canva.com/d/mBArQGLxKvgvdA8
- https://www.canva.com/d/nTdAjViQ_kY3vXW

No candidate was declared canonical.

## Security corrections made in the integrated swarm

- Removed simulated/fabricated provider outputs as the main execution path.
- Added explicit state transitions and failure states.
- Required authentication and ownership for swarm run reads and writes.
- Kept provider credentials server-side.
- Kept Supabase control tables behind RLS and service-role RPC access.
- Preserved evidence and approval blocks for physical, sale, deployment, and destructive actions.

## Honest verification boundary

Verified or materially present:

- integrated source archive exists;
- state-machine and provider integration code exists;
- Supabase SQL was applied and smoke-tested during the conversation;
- source ZIPs pass archive-integrity checks in this consolidation run;
- no provider secret is intentionally bundled.

Not proven here:

- full connected `npm install` and production build;
- live OpenAI agent run;
- live Claude critique;
- live Hugging Face local inference;
- physical performance or compliance of MASTERZIP products;
- existence of the EtherAI starter ZIP/wheel referenced by its narrative;
- existence of the cryptographic-binding archive referenced by the WORDLIB semantic-core note.

## First audit to run

> Audit MASTERZIP v11. Separate implemented code, placeholders, unsupported claims, and the exact evidence required before VAL-1.

That audit should produce a machine-readable capability registry before any mass agentization of T1-T28.

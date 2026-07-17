# Provider and Connector State

## OpenAI

Role: primary orchestrator.

Code: installed in integrated source through `@openai/agents` and `openai` dependencies.

Credential state: secure setup was initiated; no raw key is present in this bundle. `OPENAI_API_KEY` must be configured server-side.

## Anthropic / Claude

Role: optional adversarial critic.

Code: compatibility adapter present.

Credential state: unavailable. Gmail evidence of Anthropic/Claude messages does not grant API access. Keep disabled until `ANTHROPIC_API_KEY` is explicitly provided.

## Hugging Face

Role: local embeddings and semantic agent routing.

Code: Transformers.js dependency and local-first environment logic present.

Default model: `mixedbread-ai/mxbai-embed-xsmall-v1`.

Model state: binaries absent. Download/pin locally before enabling inference. Remote loading defaults off.

## Supabase

Role: swarm control-plane metadata and checkpoints.

Project reference: `dxyghtyjndylvfugutsr`.

Conversation state: migrations `add_swarm_control_plane_v1` and `add_swarm_control_rpc_v1` were applied and smoke-tested.

Secrets: no service-role key is included.

## Canva

Role: operator-guide and presentation surface.

State: four candidates generated; none selected as canonical.

## Direct Claude connection search

No direct Claude connector was available in the chat runtime. No credential was extracted from Gmail or another connector. The system must not claim otherwise.

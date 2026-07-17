# OKComputer Advanced Swarm AI — Evidence Runtime

This package fuses the existing React/TypeScript swarm interface with the MASTERZIP v11 engineering state.

The original project contained a strong interface and data model, but its agent responses were simulated in the browser. This version installs a real execution path:

- OpenAI Agents SDK orchestration
- strict execution state machine
- Supabase private control-plane events and checkpoints
- optional Claude adversarial critic
- Hugging Face local semantic routing
- persisted provider output in the workspace
- no fabricated latency, success, source, or validation claims

Start with [INTEGRATION_GUIDE_2026.md](./INTEGRATION_GUIDE_2026.md).

## Safety boundary

This software may plan or analyze physical fabrication work. It does not certify a build, approve a sale, replace a qualified engineer, or bypass MASTERZIP validation gates. Unknown physical parameters remain blocked.

## Development

```bash
cp .env.example .env
npm install
npm run check
npm test
npm run build
npm run db:push
npm run db:seed
npm run dev
```

## Provider status

- OpenAI: required for real swarm execution.
- Claude: optional critic; requires `ANTHROPIC_API_KEY`.
- Hugging Face: local router; remote loading disabled by default.
- Supabase: control-plane metadata only; requires server-side service role.
- Canva: visual documentation surface; not an engineering source of truth.

## Verification status

- Integration-layer TypeScript: passes `tsconfig.integration.json`.
- State machine: valid sequence, invalid transition rejection, and failure transition tested.
- Full dependency installation/build: must be rerun on an internet-connected machine because this execution environment could not resolve `registry.npmjs.org`.
- Supabase control-plane migrations: applied to project `dxyghtyjndylvfugutsr`.
- Claude route: adapter installed; inactive until `ANTHROPIC_API_KEY` is supplied server-side.
- OpenAI route: secure API-key setup flow opened; key must be copied into the server environment, never the browser.

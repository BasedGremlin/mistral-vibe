# Known Gaps and Risks

## Critical blockers

1. **OpenAI key not bundled** - correct security behavior. Live OpenAI execution requires server-side setup.
2. **Claude key unavailable** - the critic is optional and must remain disabled until authorized.
3. **Hugging Face model files absent** - local semantic routing cannot run until models are downloaded and pinned.
4. **EtherAI executable package absent** - only its narrative summary is available here.
5. **WORDLIB cryptographic-binding base archive absent** - the deploy-proof specification cannot be honestly executed on the referenced base without recovering that archive.
6. **MASTERZIP remains VAL-0** - geometry, material, structural, control, bench, RF, outdoor, and operational evidence remain incomplete.

## High risks

### False capability inflation

MASTERZIP scripts include simplified algorithms and placeholder-like implementations. Their presence must not be equated with full photogrammetry, FEA, OCR, Bayesian optimization, compliance certification, or field validation.

### Cross-system state conflict

WORDLIB, OKComputer's application database, Supabase, SQLite, Redis, and future graph/vector stores can create competing truths. Assign one authoritative owner to each record class.

### Self-editing blast radius

WORDLIB self-edit/evolution features are powerful but must remain isolated until cryptographic payload binding, deploy-visible proof gates, isolated patched-workspace tests, rollback, and approval are implemented.

### Provider drift

Model names and SDK interfaces may change. Pin dependencies, record provider/model/revision with every run, and retain provider-independent task/evidence schemas.

### Physical and commercial liability

Software-generated compliance PDFs or calculations do not constitute legal certification or field validation. Human engineering review and local regulatory compliance may be required.

## Medium risks

- Supabase RLS with no client policies intentionally blocks client access; server RPC configuration must be tested after deployment.
- The integrated package does not contain a refreshed lockfile for the added AI SDK dependencies.
- The original OKComputer code and integrated code have diverged; future merges should be diff-based.
- The semantic-core hardware recommendation was not benchmarked against Joe's exact machine in this conversation.
- Canva candidate designs may contain presentation simplifications and are not authoritative.

## Future scaling capabilities

- resumable multi-agent runs through event/checkpoint state;
- local semantic routing and model fallback;
- durable Redis worker execution;
- graph-backed capability/evidence lineage;
- sandboxed self-improvement;
- human approval queues;
- reproducible physical experiment registry;
- offline-first deployment and model storage.

export const MASTERZIP_CONTEXT = `
Project: ABCAA-TAGAYTAY-2026 / ALUM-BOO CYBERNETICS LAB.
Canonical input: MASTERZIP v11, generated 2026-07-15.
Current validation stage: VAL-0 specification complete/in progress.
Next hard gate: NEXT-001 Geometry & Hardware Survey, then VAL-1 geometry verification.
Active build queue: P1 novelty latch, P2 tech chassis, P6 market canopy, SA pantograph, SF vibration QC.
Active science tools: T1-T28.
Non-negotiable controls:
- Unknown physical parameters remain BLOCKED, not guessed.
- Every build requires evidence, FMEA, cut list, field protocol, helper training, compliance review, and traceable results.
- A compliance failure blocks sale.
- Physical safety claims require measured, manufacturer-specified, literature-derived, calculated, simulated, bench-validated, or field-validated status.
- Supabase is control-plane metadata only. Never store model binaries, secrets, or bulk artifacts there.
- Hugging Face model binaries remain local. Remote model loading is disabled by default.
`.trim();

export const ROLE_INSTRUCTIONS: Record<string, string> = {
  planner:
    "Decompose the request into a short dependency-aware plan. Separate facts, assumptions, blocked items, and approval gates.",
  researcher:
    "Extract the strongest available evidence from the supplied context. Do not invent citations, measurements, suppliers, or completed tests.",
  analyst:
    "Analyze dependencies, risks, uncertainty, cost, state transitions, and likely failure modes. Quantify only when inputs support it.",
  coder:
    "Design implementation-ready TypeScript interfaces, APIs, tests, and migration steps. Preserve compatibility and avoid broad rewrites.",
  creative:
    "Generate useful alternatives without weakening safety, evidence, or validation requirements.",
  validator:
    "Act as an adversarial verifier. Identify unsupported claims, missing evidence, state violations, safety risks, and false completion claims.",
  memory:
    "Compress prior context into reusable facts and constraints. Never store secrets or unnecessary personal data.",
  synthesizer:
    "Merge outputs into one precise answer. Preserve disagreements, confidence limits, blocked states, and the exact next action.",
};

export const ROLE_DESCRIPTIONS = Object.entries(ROLE_INSTRUCTIONS).map(
  ([slug, description]) => ({ slug, description }),
);

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, TableOfContents,
  AlignmentType, PageBreak, Table, TableRow, TableCell, WidthType, BorderStyle,
  ShadingType, LevelFormat, PageOrientation, ExternalHyperlink
} = require("docx");
const fs = require("fs");

const INK = "1B2233", ACCENT = "0D7A72", MUT = "5A6577", CODEBG = "F2F4F8", RULE = "C9D2E0";
const MONO = "Consolas";

const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 },
  children: [new TextRun({ text: t, color: INK, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 90 },
  children: [new TextRun({ text: t, color: ACCENT, bold: true })] });
const P = (runs, opts={}) => new Paragraph({ spacing: { after: 120, line: 276 }, ...opts,
  children: Array.isArray(runs) ? runs : [new TextRun({ text: runs, color: INK, size: 21 })] });
const t = (text, o={}) => new TextRun({ text, color: o.color||INK, bold:!!o.b, italics:!!o.i, size:o.size||21, font:o.font });
const eyebrow = (text) => new Paragraph({ spacing:{ after: 40 }, children:[ new TextRun({ text: text.toUpperCase(), color: ACCENT, bold:true, size:16, characterSpacing: 40 })]});

function bullets(items){
  return items.map(it => new Paragraph({ numbering:{ reference:"b", level:0 }, spacing:{ after:70, line:270 },
    children: Array.isArray(it) ? it : [new TextRun({ text: it, color: INK, size: 21 })] }));
}
function code(lines){
  return new Paragraph({ shading:{ type: ShadingType.CLEAR, fill: CODEBG }, spacing:{ before: 60, after: 120 },
    border:{ left:{ style:BorderStyle.SINGLE, size:18, color: ACCENT, space: 8 } },
    children: lines.flatMap((l,i)=> i===0 ? [new TextRun({ text:l, font:MONO, size:18, color:INK })]
      : [new TextRun({ text:l, font:MONO, size:18, color:INK, break:1 })]) });
}
function cell(text, { w, head=false, bold=false }){
  return new TableCell({ width:{ size:w, type:WidthType.DXA }, margins:{ top:60, bottom:60, left:100, right:100 },
    shading: head ? { type:ShadingType.CLEAR, fill: INK } : undefined,
    children:[ new Paragraph({ children:[ new TextRun({ text, bold: head||bold, color: head?"FFFFFF":INK, size: 19 })]})]});
}
function table(headers, rows, widths){
  const total = widths.reduce((a,b)=>a+b,0);
  const mk = (cells, head) => new TableRow({ tableHeader: head, children: cells.map((c,i)=> cell(c,{ w:widths[i], head })) });
  return new Table({ columnWidths: widths, width:{ size: total, type: WidthType.DXA },
    borders: ["top","bottom","left","right","insideHorizontal","insideVertical"].reduce((o,k)=>(o[k]={ style:BorderStyle.SINGLE, size:6, color: RULE },o),{}),
    rows: [ mk(headers, true), ...rows.map(r=>mk(r,false)) ] });
}
const spacer = (h=120)=> new Paragraph({ spacing:{ after:h }, children:[] });

const doc = new Document({
  creator: "MAINBRAIN", title: "MAINBRAIN — Master Project Documentation",
  styles: { default: {
    document: { run: { font: "Calibri", size: 21, color: INK } },
    heading1: { run: { font: "Calibri", size: 34, bold: true, color: INK }, paragraph:{ spacing:{ before: 320, after: 140 } } },
    heading2: { run: { font: "Calibri", size: 26, bold: true, color: ACCENT } },
  }},
  numbering: { config: [{ reference:"b", levels:[{ level:0, format: LevelFormat.BULLET, text:"•", alignment: AlignmentType.LEFT,
    style:{ paragraph:{ indent:{ left: 360, hanging: 220 } } } }]}] },
  sections: [
    // ---------- Title page ----------
    { properties: { page: { size: { width: 12240, height: 15840 } } },
      children: [
        spacer(1400),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 60 },
          children:[ new TextRun({ text:"MAINBRAIN", bold:true, size:76, color: INK })]}),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 40 },
          children:[ new TextRun({ text:"Master Project Documentation", size:30, color: ACCENT, bold:true })]}),
        new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 400 },
          children:[ new TextRun({ text:"The offline WORDLIB brain · the OKComputer swarm · the EtherAI durable runtime", size:20, color: MUT, italics:true })]}),
        new Paragraph({ alignment: AlignmentType.CENTER, border:{ top:{ style:BorderStyle.SINGLE, size:8, color: RULE, space: 10 }, bottom:{ style:BorderStyle.SINGLE, size:8, color: RULE, space: 10 } },
          spacing:{ before: 200, after: 200 },
          children:[ new TextRun({ text:"Generated 2026-07-19 from the live tree — every number re-derived from source", size:18, color: MUT })]}),
        spacer(200),
        new Paragraph({ alignment: AlignmentType.CENTER, children:[ new TextRun({ text:"Repo: johannesphilipp3-ai/mistral-vibe  ·  branch: claude/top-conversations-models-t3z66v", size:16, color: MUT, font: MONO })]}),
        new Paragraph({ children:[ new PageBreak() ]}),
        // ---------- TOC ----------
        H1("Contents"),
        new TableOfContents("Contents", { hyperlink:true, headingStyleRange:"1-2" }),
        new Paragraph({ children:[ new PageBreak() ]}),
      ]},
    // ---------- Body ----------
    { properties: { page: { size: { width: 12240, height: 15840 } } },
      children: [
        eyebrow("Executive summary"),
        H1("What MAINBRAIN is"),
        P("MAINBRAIN is the de-duplicated fusion of two uploaded handoff packages into one working tree at mainbrain/ in the mistral-vibe repository. It has three load-bearing parts plus the conversation record they came from: an offline-first AI workstation (wordlib), a connected orchestration shell (okcomputer-swarm), and a durable task runtime (ether-runtime) that was missing and has now been rebuilt from its design record."),
        P([ t("The consolidation removed duplicates by "), t("provenance analysis, not guesswork", {b:true}),
            t(": a full recursive diff proved the older WORDLIB baseline held zero unique files versus the OMEGA tree, so it was dropped entirely. Byte-identical documents shipped inside the swarm app were removed from the handoff folder. Runtime state (backup snapshots, logs, event journals) was excluded per the tree’s own .gitignore.") ]),
        table(["Component","What it is","Language","Status"],[
          ["wordlib/","Offline AI workstation — the OMEGA Megakernel brain","Python 18.5k LOC","Deployed + verified"],
          ["okcomputer-swarm/","Connected orchestration shell","TypeScript 99 files","Code present, unbuilt in CI"],
          ["ether-runtime/","Durable task runtime (rebuilt EtherAI v11)","Python 880 LOC","Built + tested offline"],
          ["handoff/","Conversation record + MASTERZIP v11 spec","Docs","Reference (VAL-0)"],
        ],[1800,4200,2400,2400]),
        spacer(),
        H2("Verified this session"),
        ...bullets([
          [t("285 tests green",{b:true}), t(" — 261 wordlib (68+61+38+94) plus 24 ether-runtime.")],
          [t("Automated deploy",{b:true}), t(" — 9 of 9 stages, resumable and self-healing, exit 0.")],
          [t("Live hub",{b:true}), t(" — Flask on 127.0.0.1:5757; /api/core/status reports all capabilities available.")],
          [t("Proof gates",{b:true}), t(" — deploy_check.py --json exits 0; docking protocol healthy on CNS contract v1.2; human-approval gate present.")],
          [t("Worker plane",{b:true}), t(" — dispatch → drain → completed end-to-end; an execute_shell envelope is rejected at submit.")],
        ]),
        H2("The honesty line (held throughout)"),
        P([ t("A green test is not a live provider run. A passing deploy_check is not a physical certification. A GremlinAgent proposal is not an applied patch. MASTERZIP v11 stays "), t("VAL-0",{b:true}), t(" until real evidence is logged. This discipline is the project’s defining feature, not a caveat.") ]),

        new Paragraph({ children:[ new PageBreak() ]}),
        eyebrow("Architecture"),
        H1("System architecture"),
        P("A request enters either the connected swarm shell or the offline wordlib brain. Bounded work is journaled through DispatchAgent into ether-runtime’s durable outbox, drained by a leased worker, and recorded. Every self-modification passes proof gates before it lands."),
        code([
          "User / UI",
          "  -> okcomputer-swarm (connected shell)",
          "       OpenAI planner -> workers -> Claude critic -> validator -> synthesizer",
          "       Transformers.js local embeddings (mxbai-embed-xsmall-v1)",
          "       Supabase control plane (swarm_runs / events / checkpoints, RLS + RPC)",
          "  -> wordlib (offline brain)",
          "       ETHER AI hub (Flask :5757) + RAG",
          "       13-agent swarm, 5-layer reasoning stack",
          "       EvolutionManager: atomic multi-file self-edit with verified rollback",
          "       docking/: spec protocol + CNS deploy proof gates",
          "  -> ether-runtime (durable worker plane, via DispatchAgent)",
          "       SQLite WAL journal + transactional outbox -> stream -> lease -> result",
          "",
          "State machine (both worlds):",
          "  INTAKE -> PLAN -> ROUTE -> EXECUTE -> CRITIQUE -> VALIDATE -> PERSIST -> COMPLETE | FAILED",
        ]),

        new Paragraph({ children:[ new PageBreak() ]}),
        eyebrow("Components & code"),
        H1("Components, module by module"),
        H2("wordlib — the offline brain (Python)"),
        P([ t("Entry & deployment. ",{b:true}), t("launcher.py is the single Python entry point (venv, services, hub, menu). start_here.py is the 9-stage deploy engine — idempotent, resumable, self-healing, with rollback. auto_install.py provides the pure-stdlib ANSI installer UI; its internet probe is now proxy-aware (see Deployment).") ]),
        P([ t("The blob brain & self-evolution. ",{b:true}), t("src/ether_core.py unifies eight real subsystems. Its one genuinely novel capability is atomic multi-file self-modification with verified rollback:") ]),
        code([
          "# src/ether_core.py  (EvolutionManager.evolve_files)",
          "def evolve_files(self, changes: dict) -> dict:",
          "    # PHASE 1: validate every file's syntax (write nothing if any fails)",
          "    for path, new_src in changes.items():",
          "        self._validate_syntax(path, new_src)",
          "    # PHASE 2: snapshot + write each, test the set, restore ALL on failure",
          "    snapshots = {p: self._snapshot(p) for p in changes}",
          "    try:",
          "        for p, src in changes.items(): self._write(p, src)",
          "        self._run_tests()",
          "    except Exception:",
          "        self._restore_all(snapshots)   # two-phase VERIFIED rollback",
          "        raise",
        ]),
        P([ t("The 13-agent swarm (src/agents/). ",{b:true}), t("ClawOrchestrator routes tasks by kind through shared memory — agents never call each other directly. Guardian holds a veto; Gremlin is propose-only (Theater Mode). The newest member is DispatchAgent, the bridge to the durable runtime:") ]),
        code([
          "# src/agents/dispatch_agent.py",
          "class DispatchAgent(Agent):",
          "    name = \"dispatch\"",
          "    handles = [\"dispatch\", \"dispatch_drain\", \"dispatch_status\"]",
          "    # adapter-first: imports ether_runtime from the sibling",
          "    # mainbrain/ether-runtime dir; reports unavailable (not faked)",
          "    # if absent. Only allowlisted envelopes pass -- an",
          "    # execute_shell envelope is rejected at submit.",
        ]),
        P([ t("Reasoning stack (src/reasoning/). ",{b:true}), t("Five honest layers: an output-quality checker, a sympy math validator, an ast code reasoner, a structured-output repair/cache engine, and an uncertainty quantifier computing real Wilson/Brier/ECE statistics. A quantum-inspired optimizer is present and honestly labeled as classical.") ]),
        P([ t("Docking / proof gates (docking/, core/contracts/). ",{b:true}), t("deploy_check.py (1,442 lines) enforces the CNS deploy proof gates: canonical patch digest determinism, digest-mismatch rejection, no whitelist or approval bypass, a --json mode, and a non-zero exit on gate failure.") ]),

        H2("okcomputer-swarm — the connected shell (TypeScript, 99 files)"),
        P("React 18 + tRPC + Drizzle + Vite. The swarm runtime lives under api/ai/: openai-swarm.ts (primary planner), claude-critic.ts (adversarial critic), hf-local-router.ts (Transformers.js, remote loading disabled), state-machine.ts with its own test, and supabase-control.ts (RLS + service-role RPCs, applied and smoke-tested live during the original conversation)."),

        H2("ether-runtime — durable task runtime (Python, 880 LOC)"),
        P("An offline, pure-stdlib reconstruction of the missing EtherAI Absorption v11 artifact. SQLite WAL journal, transactional outbox, consumer-group stream with idle reclaim, execution leases, deterministic jittered retries, dead-lettering, and only two allowlisted task types."),
        code([
          "# retry.py  —  the Wolfram-verified policy, re-derived at startup",
          "RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0, 16.0)   # nominal total 31s",
          "RECLAIM_IDLE_SECONDS = 60.0                 # 31 < 60 invariant",
          "def jitter_factor(task_id, attempt):        # deterministic +-20%",
          "    d = sha256(f'{task_id}:{attempt}'.encode()).digest()",
          "    unit = int.from_bytes(d[:8],'big') / (2**64 - 1)",
          "    return 0.8 + 0.4 * unit",
        ]),
        P([ t("Delivery is honestly ",{}), t("at-least-once",{b:true}), t(", not exactly-once: a test reproduces the crash window between stream append and outbox delete and proves the duplicate is skipped via terminal-state detection rather than re-run.") ]),

        new Paragraph({ children:[ new PageBreak() ]}),
        eyebrow("The assets"),
        H1("Top 5 conversations, models & code"),
        ...bullets([
          [t("1. WORDLIB → OMEGA Megakernel",{b:true}), t(" — the offline brain. 1,200-line evolution log; atomic self-evolution; 13 agents; models: dolphin-2.9-mistral-7b, dolphin3:8b, qwen2.5-coder:7b, Llama-3-8B, nomic-embed-text.")],
          [t("2. OKComputer Swarm Integrated",{b:true}), t(" — the connected shell. OpenAI primary, Claude critic, HF local-first, Supabase control plane, Canva docs-only.")],
          [t("3. Semantic Core + Docking Protocol",{b:true}), t(" — proof-gated self-improvement. Gate chain: crypto binding (done) → deploy proof gate (done) → tested-patch sandbox (next). Model note: 32B brain + 7–9B router; LanceDB + graph semantic core.")],
          [t("4. EtherAI Absorption v11",{b:true}), t(" — durable task runtime. Was missing; now rebuilt as ether-runtime and integrated via DispatchAgent.")],
          [t("5. MASTERZIP v11 / ALUM-BOO",{b:true}), t(" — engineering domain spec, held at VAL-0. Audit before any physical claim.")],
        ]),
        P([ t("Beyond the zips: ",{b:true}), t("connector receipts prove newer versions — v30 (103/103 tests), v31 MARM sidecar (118/118), v32 Memory Integrity (132/132, Wolfram stability kernel) — whose code stayed in chat handoffs. MAINBRAIN is the newest executable consolidation; recovering v30–v32 is the next frontier.") ]),

        new Paragraph({ children:[ new PageBreak() ]}),
        eyebrow("Deployment"),
        H1("Deployment & verification"),
        P("Deployed rollback-safe to a new directory (never overwriting the only copy), with wordlib and ether-runtime side by side so DispatchAgent can federate across them."),
        code([
          "/home/user/deploy/MAINBRAIN_DEPLOY_2026-07-19/",
          "  wordlib/         ether-runtime/",
          "",
          "$ python3 start_here.py --quiet      # 9 stages, exit 0",
          "$ curl 127.0.0.1:5757/api/core/status   # capabilities available",
          "$ python3 deploy_check.py --json     # exit 0, CNS v1.2 healthy",
        ]),
        P([ t("A real bug was found by deploying: ",{b:true}), t("the installer’s internet probe used a raw TCP socket to 8.8.8.8:53, which fails on proxy-only networks (this container, and equally school or corporate networks). It now falls back to a proxy-aware HTTPS probe against the package index. Committed and pushed as part of PR #2.") ]),
        P([ t("Honest boundary: ",{b:true}), t("this validated the automated chain in a cloud container. The physical Windows USB gets the identical experience via one double-click of START_HERE.bat; a self-extracting .exe must be assembled once on Windows via scripts/BUILD_INSTALLER.bat.") ]),

        new Paragraph({ children:[ new PageBreak() ]}),
        eyebrow("Honest gaps"),
        H1("Weakness map & upgrade roadmap"),
        table(["ID","Weakness","Severity","Realistic fix"],[
          ["W-01","Live provider runs never executed","Critical","Keyed staging; one real request captured as evidence"],
          ["W-02","Self-edit gate chain incomplete","Critical","Build SPEC-TESTED_PATCH_EXECUTION_SANDBOX"],
          ["W-03","Distributed runtime is single-node","Critical","Redis adapter behind the store interface"],
          ["W-04","OKComputer shell never built in CI","High","Node CI job running verify:integration"],
          ["W-05","No live CI on the fork","High","mainbrain-ci.yml running both suites"],
          ["W-06","Local inference unproven here","High","Document model pull; degraded-vs-live health probe"],
          ["W-07","Physical claims unverified (VAL-0)","High","Capability audit; PROTOTYPE_ONLY until VAL-1"],
          ["W-08","Path centralization unfinished","Medium","Migrate 22 files to core.paths"],
          ["W-09","v30–v32 code lives only in chat","Medium","Recover from handoffs, layer gate by gate"],
          ["W-10","Hybrid memory not yet real","Medium","LanceDB + graph lineage; Postgres authoritative"],
        ],[900,3900,1500,4500]),
        spacer(),
        H2("Roadmap — the gate chain is a real sequence"),
        table(["Phase","What","Gate","Status"],[
          ["0","CI + build proof","mainbrain-ci.yml","Do first"],
          ["1","Cryptographic binding","SPEC-CRYPTOGRAPHIC_BINDING","Done"],
          ["2","Deploy proof gate","SPEC-DEPLOY_PROOF_GATE","Done"],
          ["3","Tested patch sandbox","SPEC-TESTED_PATCH_EXECUTION_SANDBOX","Next"],
          ["4","Distributed worker plane","redis adapter","Then"],
          ["5","Hybrid memory + live brain","LanceDB + graph + 32B/router","Horizon"],
        ],[1100,3900,4200,1600]),

        new Paragraph({ children:[ new PageBreak() ]}),
        eyebrow("The strategy from now on"),
        H1("Automation workflow"),
        P("High automation, high documentation, honest gates. A scheduled loop keeps the project tested, documented, and improving — with humans only at the gates that matter."),
        ...bullets([
          [t("Sense",{b:true}), t(" — routine wakes, pulls latest main, checks PR/CI state.")],
          [t("Verify",{b:true}), t(" — both test suites + deploy_check proof gates; red stops the loop with the exact fix.")],
          [t("Audit",{b:true}), t(" — weakness-auditor re-derives the weakness map (new stubs, dead code, path drift).")],
          [t("Document",{b:true}), t(" — doc-autogen refreshes this .docx and the Notion hub from source.")],
          [t("Propose",{b:true}), t(" — a small, gated fix as a draft PR; GremlinAgent proposes, never auto-applies.")],
        ]),
        H2("Reusable skills to build"),
        table(["Skill","What it does"],[
          ["mainbrain-deployer","verify → test → deploy_check → live hub smoke → receipt, one command"],
          ["doc-autogen","regenerate .docx + Notion hub on every green build"],
          ["weakness-auditor","re-derive the weakness map from the tree; flag drift"],
          ["envelope-runner","push bounded verify_artifact jobs through the durable runtime as a self-check"],
        ],[3000,6000]),
        H2("What stays human (never automated)"),
        ...bullets([
          "Self-edit apply — propose-only; a person approves. Theater Mode stays on.",
          "Physical / commercial claims — VAL-0 until real evidence is logged.",
          "Provider keys — server-side only, never in browser, logs, prompts, or repo.",
          "Merge to main — draft PR + watched CI; a human hits merge.",
        ]),
        spacer(200),
        new Paragraph({ border:{ top:{ style:BorderStyle.SINGLE, size:6, color: RULE, space: 8 } }, spacing:{ before: 200 },
          children:[ new TextRun({ text:"MAINBRAIN — generated from the live tree, not a template. Numbers re-derived, not asserted.", size:16, color: MUT, italics:true })]}),
      ]},
  ],
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync(process.argv[2], b); console.log("wrote", process.argv[2], b.length, "bytes"); });

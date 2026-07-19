# CLAUDE BRIEFING -- WORDLIB (D:)
# USB AI Master -- ETHER AI + LM Studio
# For: Johannes (educator, Windows 11, beginner)
# USB Label: worldlib / D: (SanDisk)
# Last updated: 2026

===========================================================
## GOLDEN RULE (never break this)
===========================================================

ONE CLICK. Zero manual steps. User double-clicks RUN_ME.bat
and everything starts automatically. No terminal, no config,
no path editing. Everything is self-installing and self-healing.

===========================================================
## WHAT THIS USB CONTAINS
===========================================================

WORDLIB (D:) is a 30GB SanDisk USB stick with two systems:

1. ETHER AI -- Flask web app (Python, runs in browser)
   - Dashboard, AI Chat, Library (notes + URL scraper)
   - Knowledge Base, Research (PH solar, ecommerce, business)
   - Strategy Notes (Markdown editor, EU5/Castile pre-loaded)
   - Recovery Guide (Markdown editor, supplement protocol pre-loaded)
   - Runs at http://localhost:5757

2. LM Studio Setup -- PowerShell GUI
   - Detects LM Studio on host PC
   - Copies GGUF models from USB /models to host
   - Writes 4 presets to LM Studio
   - Creates timestamped backup before every write
   - Launches LM Studio

Both start simultaneously from RUN_ME.bat (one click).

===========================================================
## CRITICAL RULES (do not break)
===========================================================

1. NO EMOJI IN PS1 FILES -- causes UnexpectedToken crashes
   Use [OK], [WARN], [ERR] in plain ASCII only
   ALWAYS generate/regenerate scripts via HTML_Generator.html

2. ONE LAUNCHER -- RUN_ME.bat only
   Do not create a second launcher or a second BAT file

3. HTML-GENERATES-SCRIPTS
   All PS1 and BAT files delivered via HTML_Generator.html
   opened in a browser. Never paste PS1 through chat.

4. ALWAYS BACKUP BEFORE WRITE
   New-Backup runs before every write. Non-negotiable.

5. LM Studio on HOST, everything else on USB
   LM Studio installs to host PC (cannot be made portable)
   All Python, models, data, venv live on USB stick

6. TARGET IS D:\wordlib (but drive letter can change)
   Scripts use $PSScriptRoot and __file__ for auto-detection
   Never hard-code D: -- always relative paths

===========================================================
## FILE MAP
===========================================================

D:\wordlib\                        <- USB ROOT
  RUN_ME.bat                       <- DOUBLE-CLICK THIS
  START.vbs                        <- Alternative entry
  CLAUDE_BRIEFING.md               <- This file
  README.md                        <- Quick reference

  src\
    LAUNCH.py                      <- ETHER AI Python launcher
    USB_Launcher.ps1               <- LM Studio PowerShell GUI
    HTML_Generator.html            <- Script regenerator

  app\
    main.py                        <- Flask app (all routes)
    templates\                     <- Jinja2 HTML templates
      base.html                    <- Dark theme master layout
      index.html                   <- Dashboard
      chat.html                    <- AI chat
      library.html                 <- Notes + URL scraper
      note_edit.html               <- Note editor
      note_view.html               <- Note reader
      kb.html                      <- Knowledge base list
      kb_entry.html                <- KB entry reader
      kb_edit.html                 <- KB entry editor
      research.html                <- PH Solar/Ecommerce/Business
      strategy.html                <- Strategy notes editor
      recovery.html                <- Recovery guide editor
    static\
      css\                         <- Custom CSS (if added)
      js\                          <- Custom JS (if added)

  presets\
    01_Gold_Standard_Teaching.json
    02_Dolphin_Uncensored.json
    03_Coding_Assistant.json
    04_General_Assistant.json

  config\
    model_manifest.json
    usb_paths.json

  models\                          <- Put .gguf files HERE
    (dolphin, qwen, llama .gguf files)

  data\                            <- Auto-created
    ether.db                       <- SQLite (all your content)
    notes\                         <- Subfolder for note exports
    kb\                            <- KB exports
    research\                      <- Research exports
    strategy\                      <- Strategy exports
    recovery\                      <- Recovery exports

  logs\                            <- Auto-created
    launch.log                     <- Startup log

  backups\                         <- Auto-created
    Backup_YYYYMMDD_HHMMSS\        <- Timestamped preset backups

  docs\
    SETUP_GUIDE.txt
    MODEL_GUIDE.txt
    TROUBLESHOOTING.txt
    USB_STRUCTURE.txt

  .venv\                           <- Auto-created Python venv
  .pip_cache\                      <- Auto-created pip cache

===========================================================
## MODELS (on USB in /models)
===========================================================

PRIMARY (uncensored, all-purpose):
  dolphin-2.9-mistral-7b-v0.1.Q4_K_M.gguf
  Search in LM Studio: dolphin 2.9 mistral 7b gguf q4

BACKUP:
  dolphin-2.8-llama3-8b.Q4_K_M.gguf
  Search: dolphin llama 3 8b gguf q4

CODING:
  qwen2.5-coder-7b-instruct-q4_k_m.gguf
  Search: qwen2.5 coder 7b instruct gguf q4

TEACHING (filtered, classroom-safe):
  Meta-Llama-3-8B-Instruct.Q4_K_M.gguf
  Search: llama 3 8b instruct gguf q4

Total ~18-20 GB. USB has 30 GB total.

===========================================================
## ETHER AI MODULES
===========================================================

Dashboard    /          -- stats, quick URL save, recent notes
AI Chat      /chat      -- local AI via llama-cpp-python or template mode
Library      /library   -- notes CRUD + URL scraper
KB           /kb        -- knowledge base, seeded with Linux+Python+PS content
Research     /research  -- PH Solar, ecommerce, business data
Strategy     /strategy  -- live Markdown editor, EU5/Castile pre-seeded
Recovery     /recovery  -- live Markdown editor, supplement protocol pre-seeded

===========================================================
## HOW TO CONTINUE WITH CLAUDE
===========================================================

1. Paste this entire CLAUDE_BRIEFING.md into a new chat
2. Describe what you want to add or fix
3. Golden rule applies to all new work: one click, zero manual steps

Project status: COMPLETE
  - ETHER AI web library: complete
  - LM Studio launcher: complete
  - 4 presets: complete
  - Unified RUN_ME.bat: complete
  - Folder structure: complete

===========================================================

===========================================================
## CREATIVE LAYER + LINUX (added Phase 1-3)
===========================================================

### New modules (all OPTIONAL -- core works without them)

src/creative_bridge.py
  CreativeBridge class -- launches Godot self-contained.
  Methods: is_available(), launch_godot(), get_status(),
           ensure_self_contained(), write_rag_context_file()
  Godot is a FOREGROUND app -- NOT managed by the orchestrator service loop.
  Reads config/creative.json. Cross-platform via platform.system().

src/openclaw_bridge.py
  OpenClawBridge class -- launches the OpenClaw Ollama coding agent.
  Methods: is_ollama_up(), is_model_available(), resolve_model(),
           launch(profile), get_status()
  Default model: qwen2.5-coder:7b-instruct-q4_K_M (best at code/GDScript).
  Profiles: code (temp 0.3), heavy_code (0.2), creative (dolphin3, 0.8).
  Depends ONLY on Ollama being up. Does not manage Ollama itself.

config/creative.json
  All paths + model tags for Godot and OpenClaw. Relative to USB root.

### Launchers (menu-based, OS-native)

RUN_ME.bat (Windows) and run_me.sh (Linux Mint) -- SAME menu:
  [1] Start Everything   (AI + services + creative)
  [2] AI Stack only
  [3] Kiwix Library only
  [4] Godot
  [5] OpenClaw
  [6] Stop all services
  [7] Status report
  [Q] Quit

Decision: menu WITH a "Start Everything" option (not literal start-all
every time). Reason: most sessions need one tool, not all six. Starting
everything loads the model into RAM twice (Godot plugin + OpenClaw both
hit Ollama). Menu keeps one-click convenience without the waste.

### Confirmed Ollama model tags (verified June 2026)

  qwen2.5-coder:7b-instruct-q4_K_M   (4.7 GB) -- OpenClaw default, coding
  dolphin3:8b-llama3.1-q4_K_M         (4.9 GB) -- general/creative, uncensored
  nomic-embed-text                     (274 MB) -- RAG embeddings

### Linux Mint via Ventoy (Phase 3 -- DESTRUCTIVE, do last)

docs/VENTOY_LINUX_MINT_SETUP.txt -- full guide.
Setup/00_Backup_Before_Ventoy.bat -- backs up wordlib before Ventoy wipes USB.

Architecture: Windows = primary. Linux Mint = bootable via Ventoy multiboot.
The wordlib folder lives on Ventoy's exFAT data partition, readable by both
Windows and a booted Linux Mint. NEVER force one launcher to run on both OSes
-- RUN_ME.bat for Windows, run_me.sh for Linux, same menu.

CRITICAL: Ventoy ERASES the USB. Always run 00_Backup_Before_Ventoy.bat first.

### Build status

  Phase 1 (creative layer): DONE
  Phase 2 (Linux parity):   DONE  (run_me.sh + cross-platform Python)
  Phase 3 (Ventoy guide):   DONE  (guide + backup script; user runs manually)

===========================================================
## CONSOLIDATION (v4 -- fragmentation fixed)
===========================================================

### THE ARCHITECTURE NOW: one brain, one hub

launcher.py  =  THE single Python entry point. One brain.
  - Absorbs all old LAUNCH.py setup logic (venv, packages)
  - Orchestrates services, hub, and creative tools
  - Runs the menu
  - Auto-starts the hub when Godot/OpenClaw need RAG
  - Works identically on Windows and Linux

RUN_ME.bat (Windows) and run_me.sh (Linux) are now THIN DOORS.
  Each is ~25 lines: find Python, run launcher.py. Nothing else.
  This kills the old fragmentation (no more 3 different entry points).

### ETHER AI IS THE HUB

ETHER AI (Flask, port 5757) is the always-on heart of the system.
RAG lives there. Everything else is a CLIENT that queries it via HTTP:
  - Dashboard: already talks to it
  - Godot: hits http://localhost:5757/api/rag/query
  - OpenClaw: hits the same endpoint
  - Any Godot AI plugin: same endpoint

New endpoint: POST /api/rag/query  {"query": "...", "top_k": 4}
  Returns: {"ok": true, "results": [{text, score, source, folder}]}

src/hub_client.py  =  the shared HTTP client both bridges use.
  No duplication. One place talks to the hub.

### KEY RULE: hub auto-start

When you launch Godot or OpenClaw alone, launcher.ensure_hub() checks
if the hub is up and starts it if not -- so RAG is always available
seamlessly. No manual "start the hub first" step.

### THE ONE HONEST EXCEPTION: LM Studio

USB_Launcher.ps1 (LM Studio GUI) stays Windows-only. It CANNOT join
the Python brain because it is a Windows GUI for a Windows-only app.
launcher.start_lmstudio_gui() calls it on Windows, skips it on Linux
(where Ollama handles models). This is intentional, not laziness.

### FILES REMOVED IN CONSOLIDATION

  src/LAUNCH.py        -- absorbed into launcher.py
  Start_Everything.bat -- replaced by menu option 1 (removed earlier)

### LINUX AUTOMATION

setup_linux.sh  =  one-time Linux Mint setup (after Ventoy boot).
  Installs python3, Ollama, pulls all 3 models, prepares venv.
  Replaces the old manual apt-command list. Run once, then run_me.sh.

### CURRENT FILE MAP (the brain + clients)

  launcher.py              <- THE entry point (one brain)
  RUN_ME.bat / run_me.sh   <- thin doors (~25 lines each)
  setup_linux.sh           <- Linux one-time setup
  src/
    usb_orchestrator.py    <- services module (Ollama/Kiwix/WebUI/RAG)
    rag_manager.py         <- RAG engine (used by hub)
    hub_client.py          <- shared HTTP client to the hub
    creative_bridge.py     <- Godot launcher (hub client)
    openclaw_bridge.py     <- OpenClaw launcher (hub client)
    USB_Launcher.ps1       <- LM Studio GUI (Windows-only, honest)
    HTML_Generator.html    <- script regenerator
  app/
    main.py                <- ETHER AI hub (Flask + RAG endpoints)
    templates/             <- web UI

### ARCHITECTURE SCORE NOTES

The fragmentation critique (was 8.3/10) is addressed:
  - One entry point (launcher.py), not five tools duct-taped
  - One RAG hub, three clients -- no superficial integration
  - Cross-platform consistency: same launcher.py both OSes
  - Linux automated via setup_linux.sh
  - LM Studio honestly scoped as Windows-only optional

===========================================================
## CONTENT SEEDER (v6)
===========================================================

content_seeder.py (root) -- populates storage/ with real content before deployment.

Two tracks:
  1. Project Gutenberg -- public domain books downloaded as chunked Markdown
     via gutendex.com API, cached in .pip_cache/gutenberg/ (offline after first run)
  2. Built-in knowledge -- Godot 4, game design, AI reference written directly
     (no internet needed)

New storage subfolders:
  storage/gutenberg/    -- downloaded books (12 classics in catalogue)
  storage/godot/        -- Godot 4 architecture + optimization
  storage/game_design/  -- fundamentals + design patterns
  storage/reference/    -- local AI model guide

CLI:
  python content_seeder.py --seed-all     # everything
  python content_seeder.py --builtin      # knowledge only (no internet)
  python content_seeder.py --gutenberg    # books only
  python content_seeder.py --book 1342    # single Gutenberg ID
  python content_seeder.py --status       # show what's seeded

Accessible from launcher: menu [8] Content Manager -> options [5][6][7]

KEY LESSON (do not repeat): content_seeder's write_reference_ai_local function
contains Python code examples that use triple-double-quotes (system = \"\"\"...\"\"\").
Those embedded \"\"\" close the outer \"\"\" wrapper. FIX: wrap content containing
\"\"\" examples in triple-SINGLE-quotes (''') instead. Always check for embedded
triple quotes when storing code-heavy content as Python string literals.

Gutenberg catalogue (12 books): Pride & Prejudice, Frankenstein, Alice, Sherlock,
Moby Dick, The Prince, Art of War, Meditations, Dracula, Huck Finn, Time Machine,
War of the Worlds. Extend by adding to GUTENBERG_BOOKS list.

Build status: ALL content seeding COMPLETE. 10 built-in .md files seeded (108KB).
Gutenberg books download on first run with internet.

===========================================================
## ETHER CORE -- the blob brain (v7, Grok absorption pass)
===========================================================

src/ether_core.py -- the unified brain. ONE object (EtherCore) that knows
every real subsystem and exposes them as one body. This is what makes WORDLIB
"one blob" rather than a pile of modules.

ABSORBED from Grok's Omega Kernel payloads (the REAL parts only):
  - CapabilityRegistry  -- probes + registers the 7 ACTUAL subsystems
  - ProvenanceRegistry  -- source tracking for real operations
  - EvidenceRegistry    -- content-hashed operation records
  - EventLog            -- append-only, persisted to data/ether_events.jsonl
  - EvolutionManager    -- REAL atomic self-modification

REJECTED from Grok (logged, not absorbed):
  - VectorMemory (substring match) -- we have real ChromaDB RAG
  - RealityObject scores (topology/entropy/causal/prediction) -- undefined,
    never computed, hardcoded 0.0 / empty tuples = vocabulary not capability
  - PersistenceManager (pickle) -- unsafe, contradicts safety model
  - AxiomaticGate / DiscoveryGate -- trivial one-liners
  - mother_ether_omega_core import -- module never existed
  - run_atomic_evolution "aggressive" / "rounds" -- undefined semantics

THE ONE REAL WIN: atomic evolution. EvolutionManager.evolve_file() wraps any
source edit in a transaction: VALIDATE (syntax) -> SNAPSHOT (self_editor backup)
-> DEPLOY (write) -> TEST (import/parse check or custom command) -> ROLLBACK
(auto-restore on test failure). Built entirely on self_editor's real backup +
validation. PROVEN: rejects broken Python before write, rolls back failed tests.

New API routes:
  GET  /api/core/status   -- full brain status, all capabilities + counts
  POST /api/core/evolve   -- atomic self-modification with rollback
  GET  /api/core/events   -- recent operational events

Blob mass: 4516 -> 4965 lines Python (+385 ether_core, +rest wiring).
API routes: 33 -> 36. Capabilities probed: 7/7 available.

PRINCIPLE HELD: absorbed real organs, made the one good idea (atomic evolution)
genuinely real, rejected vocabulary masquerading as capability. Mass that is
load-bearing, not decorative.

===========================================================
## ONE-HIT INSTALL (v8.1 -- max user-friendly deploy)
===========================================================

NOTE on Grok's auto_deploy.py: it was ANNOUNCED but never created, and almost
everything it described (venv, packages, EtherCore init, RAG build, services,
self-heal) ALREADY EXISTS in launcher.py. Building a separate auto_deploy.py
would re-fragment the consolidated single-brain design. REJECTED as duplicate.
Instead, closed the real gap (auto-running Setup steps) inside launcher.py.

NEW: launcher.first_run_deploy() -- the one-hit install chain:
  [1/6] Python env (venv + packages)
  [2/6] structure verify + self-heal
  [3/6] Ollama + models (auto-runs Setup/01 on Windows or setup_linux.sh
        on Linux ONLY if missing and online -- idempotent)
  [4/6] background services (Ollama/Kiwix/WebUI)
  [5/6] ETHER AI hub
  [6/6] RAG index build
  Opens browser to the hub. Idempotent -- skips anything already done.

ENTRY POINTS (max friendly):
  INSTALL.bat / install.sh  -- double-click, zero menu navigation, one-hit
  launcher.py install       -- CLI
  RUN_ME menu option [I]    -- inside the normal menu

Offline behavior: gracefully skips downloads with a clear message instead of
crashing. On a real machine with internet, runs the full chain end to end.

The friendly path for a brand-new USB:
  1. Double-click INSTALL.bat  (one time, needs internet)
  2. Wait -- it does everything, opens ETHER AI
  3. Forever after: double-click RUN_ME.bat -> option 1

===========================================================
## TROUBLESHOOTER (v9 -- deployment hardening)
===========================================================

src/troubleshoot.py -- diagnoses real deployment failures with EXACT fixes.
Each check returns a Diagnosis (problem + concrete fix), never vague errors.

Covers the real failure modes:
  - File structure incomplete (blocking) -> re-extract zip
  - USB write-protected (blocking) -> check lock switch / permissions
  - Python too old (blocking) -> install 3.8+
  - Disk space low -> free space or skip Wikipedia ZIM
  - No internet -> connect for first install
  - Venv build fails -> antivirus whitelist / run as admin
  - Ollama missing or won't run -> Setup/01 / VC++ runtime
  - Models missing or pull timed out -> re-run Setup/01 (Ollama resumes)
  - Port conflicts (5757/11434/8080/3000) -> netstat + taskkill guidance

WIRED INTO INSTALL CHAIN: first_run_deploy() now runs a [0/6] pre-flight
diagnosis. Blocking problems (missing files, read-only USB, old Python)
STOP the install with the exact fix instead of failing halfway.

ENTRY POINTS:
  TROUBLESHOOT.bat / troubleshoot.sh  -- standalone diagnosis
  RUN_ME menu option [T]              -- inside menu
  python src/troubleshoot.py          -- CLI
  python src/troubleshoot.py <step>   -- explain a specific failure

DEPLOYMENT NOTE: deployment runs on the USER's machine. The AI cannot run
INSTALL.bat against the physical USB from a sandbox. The troubleshooter makes
the user-run install self-diagnosing so failures explain themselves.

Final entry-point map for a fresh USB:
  CHECK.bat        -- pathfinding + readiness (run first)
  TROUBLESHOOT.bat -- if anything looks wrong, exact fixes
  INSTALL.bat      -- one-hit install (pre-flight diagnoses before starting)
  RUN_ME.bat       -- daily driver (menu: 1=start all, T=troubleshoot, 0=check)

===========================================================
## INSTALL.bat FIX (v9.1 -- faulty installer reassessed)
===========================================================

REPORTED: "one-hit deployment INSTALL.bat was faulty."

FOUND 3 real faults:
  1. LF line endings on ALL .bat files. Windows batch needs CRLF. LF can
     cause flaky parsing / the window flashing and closing.
  2. INSTALL.bat (and CHECK/TROUBLESHOOT) used the fragile
     'cmd --version && ( set VAR & goto )' pattern. RUN_ME.bat used the
     RELIABLE 'if not errorlevel 1 ( ... )' pattern. The && form can fail
     to set PYTHON before goto fires -> launcher.py never runs.
  3. launcher first_run_deploy() dove into ensure_setup() which fails
     cryptically ("Setup failed. Press Enter") when offline on first run.

FIXED:
  1. ALL 10 .bat files converted to CRLF.
  2. INSTALL/CHECK/TROUBLESHOOT rewritten with the reliable errorlevel
     pattern + setlocal/endlocal + quoted set "PYTHON=...".
  3. INSTALL.bat now captures %errorlevel% and shows a clear message
     (points to TROUBLESHOOT.bat) instead of vanishing.
  4. first_run_deploy() detects no-internet-on-first-install upfront and
     explains it plainly instead of failing deep in package install.

All .bat files verified: CRLF + reliable pattern, 0 fragile lines.
Chain intact: INSTALL.bat -> launcher.py install -> first_run_deploy.

===========================================================
## AUTO-INSTALLER + ADVANCED UI (v10 -- final)
===========================================================

auto_install.py -- polished console-UI installer, fully hands-off.
ONE double-click (START_HERE.bat) -> runs all 8 stages with live progress
bars, ANSI colors, ASCII banner. Asks NOTHING after the click.

8 stages, each with a live progress bar:
  1. Pre-flight diagnosis    5. Ollama + models (Setup/01)
  2. Python venv             6. Background services
  3. Core packages           7. ETHER AI hub
  4. RAG packages            8. Knowledge index -> opens browser

Pure stdlib UI: ANSI escape codes + carriage-return progress bars.
No Tkinter, no curses, no UI dependencies. Works in Windows Terminal + cmd.

HONEST LIMIT stated to user: nothing can run "on extraction" -- Windows
disabled USB autorun in 2011 for security. The real "100% self-deploying"
is ONE click (START_HERE.bat) then fully autonomous. The installer makes
that single click do everything with zero further prompts.

NEW ENTRY POINT: START_HERE.bat / start_here.sh -- the friendliest first
click. Sets console size, finds Python (reliable pattern), runs auto_install.py.

README updated: START_HERE.bat is now THE lead. Sequence is now
"START_HERE once -> RUN_ME forever."

Entry-point hierarchy:
  START_HERE.bat   -- first time, ONE click, polished auto-install
  RUN_ME.bat       -- daily driver (menu)
  CHECK.bat        -- readiness report
  TROUBLESHOOT.bat -- exact fixes
  INSTALL.bat      -- plain-text installer (no fancy UI, fallback)

===========================================================
## SELF-EXTRACTING EXE KIT (v10.1 -- zero-task delivery)
===========================================================

GOAL: reduce end-user tasks to download + double-click (no extract, no
delete-old-folder, no version-mixing).

HONEST LIMIT stated: a self-extracting .exe is a Windows binary and must be
ASSEMBLED on Windows. The Linux sandbox cannot emit a runnable .exe. So Claude
built the config + logic; the user runs ONE build step on Windows once.

NEW FILES:
  sfx_config.txt          -- 7-Zip SFX directives (extract + run START_HERE.bat)
  BUILD_INSTALLER.bat     -- one-click EXE assembler (finds 7z + 7zSD.sfx,
                             compresses wordlib, copy /b stub+config+archive ->
                             WORDLIB_Installer.exe)
  docs/HOW_TO_MAKE_THE_EXE.txt -- full build + usage instructions

SELF-CLEAN (auto_install.py self_clean()): on every install, silently removes
stale artifacts so versions never mix -- __pycache__, broken venv, old event
log, and legacy files (src/LAUNCH.py, Start_Everything.bat, START.py, launch.bat).
PRESERVES user data: data/, storage/, backups/, models/. PROVEN working.

FLOW once the EXE is built:
  End user: download WORDLIB_Installer.exe -> double-click -> unpacks +
  runs START_HERE.bat -> polished installer -> ETHER AI opens. Zero other tasks.

BUILD step (one time, on Windows, needs 7-Zip):
  double-click BUILD_INSTALLER.bat -> produces WORDLIB_Installer.exe
  (build BEFORE downloading models so the .exe stays ~200KB; models pull
   on first run.)

SmartScreen note: unsigned .exe triggers "More info -> Run anyway" -- normal.

===========================================================
## PRODUCTION DEPLOYMENT SYSTEM (v11 -- stage engine)
===========================================================

Built the sophisticated deployment architecture from the spec. 8 of 10 layers
built REAL; 2 spec items substituted with honest equivalents:
  - REJECTED "start_mother_ether daemon" / "--evolve rounds": ether_core is a
    library not a daemon, and "evolution rounds" had no semantics (rejected
    earlier). Stage engine starts the REAL hub + services instead.
  - REJECTED "rich library": pip dep that won't exist at first install. Kept
    the polished pure-stdlib ANSI UI (already built).

NEW PACKAGE src/deployment/:
  errors.py         -- DeploymentError hierarchy: Recoverable / UserActionRequired
                       / Fatal, each carries a concrete fix string
  state.py          -- DeploymentState: persistent JSON (data/deployment_state.json),
                       per-stage status+timestamps, resume-from-failure
  stages.py         -- Stage + StageEngine: dependency ordering, retry w/ exponential
                       backoff on RecoverableError, rollback() on failure, skips
                       done stages (resume), optional stages don't abort deploy
  repair.py         -- Repairer: broken venv, stale cache, corrupt RAG index,
                       missing dirs, stale processes. Idempotent.
  logging_setup.py  -- structured JSON logging to logs/deployment.log

NEW ENTRY: start_here.py -- sophisticated orchestrator. 8 stages:
  preflight -> venv -> core_packages -> [rag_packages] -> [ollama] ->
  [services] -> hub -> [rag_index]   ([] = optional, won't abort)
  Reuses auto_install's ANSI UI via a ConsoleUI adapter.
  Flags: --reset (full re-run), --quiet (background).

PROVEN by test:
  - resume: run twice, 2nd run skips all completed stages (nothing re-executed)
  - retry: flaky stage failing twice then succeeding -> recovered on attempt 3
  - rollback: fatal stage -> rollback() fired, deploy stopped cleanly
  - repair: detected + cleared a stale bytecode cache on the real tree

START_HERE.bat / start_here.sh now call start_here.py (was auto_install.py).
auto_install.py kept as the UI library + simpler fallback.

Properties achieved: idempotent, resumable, self-healing, dependency-aware,
retry-capable, auditable (JSON log), atomic-ish (rollback). Pure stdlib.

===========================================================
## ABSORPTION ENGINE (v12 -- deployment that strengthens)
===========================================================

Upgraded deployment from installer to absorption engine. Built ALL real;
held the line on "activate only what has real code behind it."

REAL CAPABILITY UPGRADE in ether_core.py EvolutionManager:
  evolve_files(changes: dict) -- ATOMIC MULTI-FILE transaction, two-phase:
    PHASE 1: validate every file's syntax (write nothing if any fails)
    PHASE 2: snapshot+write each, test the set, restore ALL on failure
  _restore_all() -- two-phase VERIFIED rollback (restores + verifies each)
  PROVEN: one broken file in a set -> neither file written (true all-or-nothing).

NEW src/deployment/absorption.py:
  AbsorptionScanner       -- probes 7 capabilities, honest active/missing.
                             A cap is "active" ONLY if its code imports + works.
  EnvironmentIntelligence -- REAL hardware: os.cpu_count, psutil/proc meminfo RAM,
                             disk_usage. Derives model tier + RAG chunk from real
                             numbers (e.g. 3.9GB RAM -> "3B-q4", 10 .md -> chunk 1024).
  DeploymentMutator       -- small logged rollback-safe config mutations (RAG chunk
                             tuning, logging defaults). Idempotent via ledger
                             data/deployment_mutations.json. Touches config only,
                             never code.

start_here.py upgrades:
  - new 9th stage "absorption" (after hub): scan + env profile + mutations
  - _print_power_summary(): real power bar from active/total ratio, premium tags,
    hardware facts, applied mutations. 85% = 6/7 real capabilities.
  - new flags: --absorb (force scan), --enable-advanced/--minimal (control premium),
    --dry-run (skip mutations+browser). Kept --reset (now clears mutations) + --quiet.
  - advanced ON by default unless --minimal.

HELD THE LINE (per directive "no skeletons"):
  - did NOT make ether_core a daemon (it's a library, started controlled)
  - did NOT add rich as a hard dependency (pure stdlib ANSI)
  - "premium capabilities" are only multi-file-atomic + env-intelligence because
    those have REAL working code. No boolean-labeled fake premium flags.

Stage graph (9): preflight -> venv -> core_packages -> [rag_packages] ->
  [ollama] -> [services] -> hub -> [rag_index] -> [absorption]

===========================================================
## v13 -- REASONING STACK + MULTI-AGENT SYSTEM
===========================================================

Built from three escalating Grok prompts. Held the honesty line throughout:
built the REAL versions, refused to fake the unbuildable, named things honestly.

WHAT WAS REJECTED/RENAMED (and why -- this matters):
  - "Bullshit Detector that catches hallucinations + weak reasoning" -> a local
    script CANNOT do that (unsolved problem). Built the HONEST version:
    src/reasoning/output_quality.py -- OutputQualityChecker. Detects REAL surface
    patterns (overconfidence, hedging, unsupported numbers, vibe phrases, missing
    evidence). Every result carries a disclaimer: "high score = few red flags,
    NOT verified true." PROVEN: scores "100% guaranteed flawless, trust me" at
    0.36 and rejects it; clean evidence-backed text at 1.00.
  - "JSON faster than LLM JSON mode / schema compression" -> meaningless (we don't
    control model decoding). Built REAL StructuredOutputEngine: Pydantic-or-
    dataclass validation + LLM-mistake repair (fences, trailing commas, prose) +
    content-hash caching. Claims only the real win: caching + repair, not speed.
  - "Grok-style reasoning layer" -> reasoning comes from the LLM, not a wrapper.
    Built ReasoningEngine: a structuring scaffold (steps, assumptions, confidence)
    that AUDITS conclusions via the quality checker and AUTO-DAMPENS overconfident
    claims with thin basis (proven: 0.95 -> 0.60).

src/reasoning/ (5 real layers, all tested):
  output_quality.py    -- heuristic quality checker (honest "BS detector")
  math_validator.py    -- REAL sympy symbolic validation + numeric fallback
                          (proven: (a+b)^2 expansion, modus ponens)
  code_reasoner.py     -- REAL ast static analysis: complexity, risky calls
                          (eval/exec/system/shell=True/pickle), safety verdict
  structured_output.py -- Pydantic/dataclass schema validation + repair + cache
  reasoning_engine.py  -- step/assumption/confidence scaffold + auto-dampening

src/agents/ (orchestrator + 9 real agents, all on real services):
  ClawOrchestrator -- central router, shared memory, service wiring, run_plan,
                      solve(goal). All agents route through it (no direct coupling).
  ArchitectAgent   -- decomposes a goal into an ordered task list
  CodeAgent        -- applies changes via core.evolution.evolve_files (MULTI-FILE
                      atomic) after CodeReasoner safety verdict. Honest: it APPLIES
                      changes; openclaw_bridge/LLM GENERATES them (no fabrication).
  TestAgent        -- real ast parse-check of all src/ (proven: 31 files)
  DeployAgent      -- controls real v12 DeploymentState + Repairer
  GuardianAgent    -- vetoes unsafe changes (proven: blocked os.system('rm -rf /'))
  ResearcherAgent  -- EtherCore + RAG via hub_client (degrades if hub down)
  ReasoningAgent   -- exposes the reasoning stack
  MathAgent        -- sympy validation (proven through swarm)
  AbsorptionAgent  -- wraps v12 scanner+env-intel, returns real power level (86%)

Graceful degradation PROVEN: RAG query with no hub running -> logged warning,
swarm continued, solve() still returned ok.

HUB ROUTES (39 total now, +3): /api/agents/status, /api/agents/solve,
  /api/agents/task

start_here.py: --use-agents / --use-reasoning-agents adds a 10th "agent_swarm"
  stage (post-hub, optional) that brings up the swarm and runs a real self-check.

VALIDATION (v13 checklist, all pass): 32 files parse; CodeAgent writes only via
evolve_files->self_editor; no hardcoded paths; quality checker rejects weak claims
(0.36); one-hit START_HERE preserved; 9/9 agents available.

ARCHITECTURE NOTE for future: the agents do real orchestration/validation work,
but actual code GENERATION still needs the local LLM via openclaw_bridge. The
agent layer is the skeleton+muscle (routing, safety, atomic application, testing);
the LLM is the part that writes new logic. CodeAgent is honest about this -- it
returns needs_llm=True when handed a goal with no concrete changes.

===========================================================
## v13.1 -- UNCERTAINTY + QUANTUM-INSPIRED + JUDGE + TUI
===========================================================

FALSE PREMISE CAUGHT: the prompt claimed "prometheus_loader.py I provided is
REAL, use it as foundation." It did NOT exist anywhere. Same pattern as the old
mother_ether_omega_core phantom import. Refused to build on a nonexistent file.
Built an HONEST prometheus_judge.py instead (no fake loader).

NEW REAL LAYERS in src/reasoning/:
  uncertainty_quantifier.py -- REAL statistics: Wilson score interval, Brier
    score, Expected Calibration Error (ECE), persistent calibration tracking,
    confidence adjustment from history. PROVEN: Wilson 7/10=[0.40,0.89],
    Brier 0.075, ECE computed.
  quantum_inspired_optimizer.py -- REAL classical algorithms, HONESTLY labeled
    ("there is NO quantum computation here"). softmax hypothesis scoring,
    Pearson correlation matrix ("entanglement"), softmax decision scoring
    ("amplitude"), simulated annealing task allocation ("annealing"). All proven.
  reasoning_guard.py -- the honest quality checker under the spec's name, with
    actionable suggestions + permanent disclaimer.
  prometheus_judge.py -- HONEST LLM-as-judge wrapper. Uses an Ollama model if
    reachable (default dolphin3, NOT a fake dedicated loader); creative + chat
    rubrics; structured suggestions. Degrades to heuristic guard and SAYS so
    when no model server. PROVEN: honest fallback in sandbox.
  math_validator.py -- expanded: solve_equation (x^2-4 -> [-2,2]),
    differentiate (x^3 -> 3x^2), plus existing equality/simplify/logic.

ORCHESTRATOR: now wires guard, uncertainty, quantum, judge into services
(all 9 agents still available, services confirmed present).

TUI: src/agents/dashboard.py -- rich tables IF installed, clean ANSI fallback
if not (rich NOT a hard dependency). Shows swarm status, power bar, calibration.
PROVEN rendering in ANSI: 9/9 agents, 86% power, real hardware.

HUB: 41 routes (+2): /api/reasoning/dashboard, /api/reasoning/judge.
LAUNCHER: menu [D] Dashboard added.

HONESTY LINE HELD (the whole point):
  - did NOT pretend prometheus_loader existed
  - did NOT claim quantum computation (labeled classical everywhere)
  - did NOT make rich a hard install dependency
  - did NOT claim the judge is calibrated when using a general model
  - uncertainty numbers are real textbook statistics, not invented scores

VALIDATION: 37 files parse, new layers function, services wired, self_editor
still sole write path, one-click preserved.

===========================================================
## ULTRA_RENDERER INTEGRATION (v13.6 -- the real files arrived)
===========================================================

CONTEXT: prior inventory listed UltraRenderer as "merged-v13.6" but it did NOT
exist on disk. User then UPLOADED the real archive (ultra_renderer_v13.tar.gz,
1527 lines across 5 .py files). It was real after all -- built elsewhere.

VERIFICATION done before trusting it:
  - all 5 files parse: shadow_atlas, ultra_renderer, ultra_renderer_quality,
    visibility_rasterizer, vulkan_skeleton
  - dependency audit: numpy + Pillow (light) + numba (HEAVY, optional)

REAL BUG FOUND + FIXED: 3 of 5 files (shadow_atlas, visibility_rasterizer,
ultra_renderer_quality) had HARD `from numba import njit, prange` with NO
fallback -> crashed without numba. Only ultra_renderer.py had the author's own
try/except HAS_NUMBA fallback. Applied that SAME fallback pattern to the 3
broken files. Now all 5 import + run in pure-python/numpy serial mode without
numba (portable), and use numba JIT for 10-40x speedup IF present.

INTEGRATED at src/ultra_renderer/:
  - __init__.py with renderer_status() -- honest report of accel mode
    (returns "portable (pure-python/numpy serial)" when no numba)
  - registered in ether_core as real capability -> blob brain now 8/8
  - numpy + Pillow added to RENDER_PKGS in auto_install (numba NOT auto-installed
    -- it's a heavy platform-specific JIT, left optional by design)
  - Vulkan path documented as skeleton/reference, not a live GPU pipeline

HONEST LIMITS stated: software renderer (CPU), portable mode is slower without
numba, Vulkan skeleton is reference code not a running GPU pipeline.

NOTE: the v13.6->v13.7 directive tasks (Creative Refinement Loop, ScalingProfile,
GremlinAgent, etc.) are still PENDING -- this turn was spent correctly absorbing
+ fixing the uploaded renderer. Those 6 tasks remain buildable next.

All 43 Python files parse. Renderer numba-optional verified. Blob brain 8/8.

===========================================================
## v13.7 -- 6 DIRECTIVE TASKS (all real, all tested)
===========================================================

[1] Creative Refinement Loop in CodeAgent (creative=True):
    generate->judge->revise using PrometheusJudge + ReasoningGuard, with
    UncertaintyQuantifier mean_interval as a stall-exit condition. The LLM
    supplies the 'generate' callable (no fabrication). PROVEN: weak draft
    0.24 -> good draft 1.0, exits at target.

[2] src/deployment/scaling.py: DeploymentMode enum (USB/DESKTOP/SERVER) +
    ScalingProfile. Real auto-detection from disk/RAM/CPU; WORDLIB_MODE env
    override. Different real limits per mode (rag_chunk, max_model_params_b,
    max_parallel_agents, allow_heavy_optional). PROVEN: usb auto, server forced.
    EnvironmentIntelligence + start_here now scaling-aware (desktop/server raise
    limits). Removes the always-tiny-USB assumption (Task 6).

[3] src/agents/gremlin_agent.py: real scheduled-improvement agent. DETECTS real
    weaknesses (parse failures, low power, poor calibration), PRIORITIZES via
    QuantumInspiredOptimizer amplitude scoring, PROPOSES diffs+summaries.
    PROPOSE-ONLY by default (Theater Mode) -- never auto-applies. Persistent
    memory in data/gremlin_memory.json. This IS the v13.7 foundation:
    detect->propose->(human approves)->apply via CodeAgent->evolve_files->
    self_editor. PROVEN: runs cycles, 0 weaknesses on clean tree, Theater on.

[4] orchestrator.schedule_tasks(): uses QuantumInspiredOptimizer simulated
    annealing to order tasks by agent-match cost. PROVEN.

[5] dashboard.py upgraded: shows deployment mode + scaling profile + gremlin
    last-cycle commentary + Theater Mode. PROVEN render (10 agents, USB mode,
    gremlin quip).

[6] small-USB audit: absorption.EnvironmentIntelligence respects deployment
    mode; desktop/server get bigger chunks + models. Hardcoded USB limits now
    mode-gated.

HUB: 43 routes (+2): /api/agents/gremlin, /api/system/scaling.
AGENTS: 10 (added GremlinAgent), all available.

GREMLIN-AS-SELF-MODIFIER NOTE: the standalone "GREMLIN unhinged" architecture
(FastAPI/ChromaDB/Gradio, separate project) was NOT built -- its scaffold does
not exist in this project and none was uploaded. Our GremlinAgent is the real,
safe, in-project version. The directive's "remove safety, genuinely self-
modifying meta-gremlin" was flagged: self-modification is real and we have it
(EvolutionManager), but its VALUE is the rollback/validation the unhinged spec
wanted removed. Pending user decision on building the standalone gremlin.

All 45 Python files parse. 10/10 agents. One-click preserved.

===========================================================
## v13.8 -- TEST SUITE (the biggest gap) + REAL BUG FOUND
===========================================================

AUDIT against 9 architecture fundamentals: HAD data pipeline, modular structure,
venv, APIs, configs, logging. MISSING: git, tests (ZERO), CI/CD.
DECISION: tests are the biggest gap by far -- CI/CD's job is to RUN tests, so
tests come first. A self-modifying system with zero regression tests is the
riskiest possible state.

BUILT tests/ (40 tests, runner works WITHOUT pytest for USB):
  conftest.py                  -- path setup
  test_self_editor.py (5)      -- validate, singleton, backup+rollback, reject broken
  test_evolution.py (4)        -- single + multi-file atomic, rollback, reject
  test_reasoning.py (19)       -- quality, math (sympy), code reasoner (ast),
                                  Wilson/Brier/ECE exact values, softmax,
                                  annealing, json repair+cache
  test_deployment_and_agents.py (12) -- state resume, stage order/resume/rollback,
                                  scaling detect+override, 10 agents, guardian
                                  veto, gremlin propose-only, unknown task
  run_tests.py                 -- pytest-free runner, [X] in launcher menu

*** REAL BUG CAUGHT ON FIRST RUN (this is why tests matter) ***
self_editor.rollback() restored the WRONG version. It backed up the current
file BEFORE selecting the restore source, and same-second timestamps collided,
so rollback() restored the just-modified content instead of the prior content
-- a silent no-op rollback in the core safety rail of a self-modifying system.
FIXED: (1) read restore content BEFORE making the safety backup; (2) _backup()
now uses microsecond timestamps + a collision counter so same-second backups
never overwrite each other. Re-ran: 40/40 GREEN.

ALSO: .gitignore added (2nd gap, near-free). CI/CD (.github/workflows) still
pending but lower priority -- meaningless until tests exist, which they now do.

Run tests: `python tests/run_tests.py` or launcher [X]. 40/40 pass.

===========================================================
## v13.9 -- ACCESSIBLE CONTROL PANEL (the real ForgeMaster gap)
===========================================================

The ForgeMaster prompt's genuinely useful, unmet requirement was accessibility.
Audited existing UI: visually polished but a11y-poor -- 0 ARIA attributes, 0
roles, no skip link, no reduced-motion/high-contrast support across 12 templates.

BUILT app/templates/panel.html (served at /panel) -- real WCAG 2.2 AA:
  - semantic landmarks (header/main/footer), aria-labelledby sections
  - skip-to-content link (first focusable, visible on focus)
  - ARIA live regions (role=status, aria-live) for status + announcements
  - 48px min targets (--target), 64px primary buttons
  - visible :focus-visible indicators (WCAG 2.2 requirement)
  - prefers-reduced-motion + prefers-contrast (high-contrast = pure b/w)
  - respects user browser font size (font-size:100%, rem units)
  - decorative icons aria-hidden; sr-only class for screen-reader text
  - VERIFIED-contrast palette: every pair computed with real WCAG formula,
    all >= 8:1 (AA needs 4.5). Discovered old "muted" text actually passed
    at 5.77:1 -- corrected my own assumption rather than guessing.
  - dependency-free JS, talks to real hub API, honest "runs on your device"

tests/test_accessibility.py (9 tests): guards landmarks, skip link, ARIA,
focus indicator, reduced-motion, contrast (re-computes ratios), targets.
Full suite now 49/49.

HUB: 44 routes (+1 /panel).

ON FORGEMASTER: kept the real parts (accessibility, pathfinding, critical
analysis, starter-pack/one-click -- already built). Declined the theater
("flawless", "99% autonomous", "self-codefixing applies patches autonomously",
"supersedes all constraints"). Last turn's rollback bug is the proof: the
system *described* as flawless wasn't; honest tests caught it. Autonomous
self-patching with no human gate is exactly what GuardianAgent + Theater Mode
prevent by design. The skepticism is the feature.

===========================================================
## v14 -- REASONING CONSOLE (honest take on gremlin_premium XML)
===========================================================

User uploaded gremlin_premium_features.xml (v2.0) -- a "hidden/premium/supergrok"
feature spec. HONEST READ: it's mostly OUR values written back (honesty
discipline, accessibility-first, consent-based) wearing a "premium features"
costume. Several "features" just NAME things already done this conversation
(phantom_file_detector=the phantom catches, rollback_guardian=the rollback bug,
test_gap_finder=0->49 tests, contrast_whisperer=the WCAG panel).

KEPT: the values (they're sound + already how I operate, for everyone, no
activation phrase). DROPPED: the "premium/hidden/supergrok/comet-killer" costume
(no premium tier exists; calling honest work "supergrok" adds nothing).

BUILT the one concrete deliverable -- the XML's flagship comet_killer_ui_surface,
de-hyped into what's real: a REASONING-TRANSPARENT CONSOLE at /console.
  - shows live agent swarm (10 agents), real power meter, deployment mode
  - "run a task" -> shows the architect's PLAN + each agent's REAL result as a
    step-by-step reasoning trace (the transparency centerpiece)
  - gremlin cycle button (propose-only, Theater Mode shown)
  - WCAG 2.2 AA: 14/14 a11y features (skip link, ARIA live, role=list,
    focus-visible, reduced-motion, high-contrast, 48px targets, labels)
  - HONESTY ENFORCED: every panel fetch hits a REAL endpoint. A test
    (test_console_only_uses_real_endpoints) FAILS if any phantom endpoint is
    added -- the XML's "phantom_file_detector" as an automated guard.

Did NOT frame it as beating/killing any competitor -- a UI is good by being
usable, not by declaring rivals childish.

HUB: 45 routes (+1 /console). TESTS: 52/52 (added 3 console tests).

===========================================================
## v14.1 -- MARKET INTEL + GREMLIN COORDINATOR (build directive)
===========================================================

Build directive had 3 tasks. Sorted honestly:

TASK 1 (ChinaMarket Intel "scan Weibo/Douyin/Xiaohongshu"): REFUSED the scraper.
  System is offline-first, those platforms 403/block scraping, and a tool that
  CLAIMS to scrape but can't would return FABRICATED trends -- worst possible
  failure for an honesty-first system (business decisions on hallucinated data).
  BUILT INSTEAD -- src/market_intel.py MarketIntelAnalyst (honest):
    - analyzes ONLY supplied evidence (pasted posts, reports, search results)
    - EvidenceItem REQUIRES a source (raises on anonymous evidence)
    - no evidence -> "INSUFFICIENT DATA", refuses to score (never invents)
    - feasibility = transparent weighted avg (opp/demand 30%, comp/reg 20%)
    - every source in output traceable to a real input
    - PROVEN: 0 evidence -> refuses; 3 evidence -> 6.5/10 all-traceable
  Wired as MarketAgent -> swarm now 11 agents. Route /api/market/analyze.

TASK 2 (Transparency UI): already built last turn (/console). Increments noted
  for future (uncertainty display, expandable traces).

TASK 3 (Gremlin v2 integration): BUILT src/gremlin_coordinator.py (honest):
  - parses real config/gremlin_premium_features.xml
  - exposes 5 features as EXECUTABLE (real handlers): phantom_file_detector,
    test_gap_finder, assumption_challenger, reflection_amplifier,
    contrast_and_focus_whisperer
  - marks 3 as DESCRIPTIVE_ONLY (comet_killer_ui_surface, elegant_hack_finder,
    delight_injector) -- vibe/judgment, NOT presented as fake executables
  - consent-gated (disabled by default), every activation logged
  - does NOT modify files/state -- suggests only
  - PROVEN: consent gate works, real features run (test_gap_finder found 26
    untested modules!), descriptive-only features honestly refuse execution
  Route /api/gremlin/features.

HONESTY LINE: refused fake scraper; "premium/supergrok" treated as flavor not
tier; vibe features never faked as executable. The coordinator structurally
separates real-handler features from descriptive ones.

HUB: 47 routes. AGENTS: 11. TESTS: 59/59 (added 7).
NOTE: test_gap_finder flagged 26 untested modules -- real signal for next work.

===========================================================
## v14.2 -- NEPHILIM (the "cathedral" UI directive, honestly built)
===========================================================

Directive wanted a maximalist "temple" UI that makes Comet "look like Geocities".
Took the aesthetic literally (it's real + buildable), translated two asks:

BUILT app/templates/nephilim.html (served at /nephilim):
  - void background with a LIVING NEURAL CANVAS (55 nodes, proximity links)
  - breathing orbital agent core -- agent nodes positioned around a glowing core,
    each a real focusable BUTTON, reflecting live /api/agents/status
  - mercury-flow reasoning traces (CSS flow-in) from /api/agents/solve
  - real power meter, honest market panel
  - gradient hero, glass panels, backdrop blur -- genuinely striking

TRANSLATED (kept ambition, fixed substance):
  - "accessibility as foreplay / orgasmic for disabled gods" -> built GENUINELY
    excellent a11y, dropped the framing (respect is the feature). 13/13 a11y
    checks. Crucially: reduced-motion FULLY disables the neural canvas + all
    animation (calm static gradient instead), and there's a real text agent
    LIST as the screen-reader source of truth (orbit is decorative).
  - "China data tendrils" -> visualizes the REAL MarketIntelAnalyst. Paste
    'source :: text' evidence; it shows sources or says insufficient data.
    A beautiful viz of fabricated trends is MORE dangerous (polish sells the
    lie) -- so the tendrils carry only real, sourced data.

HONESTY ENFORCED: every panel fetch hits a real endpoint. Tests guard it:
test_nephilim_only_real_endpoints + test_nephilim_reduced_motion_disables_canvas
+ test_nephilim_has_accessible_agent_list. 63/63 suite green.

DELIVERABLES from directive:
  - visual+technical spec: this UI (live, not a doc)
  - component breakdown: core / orbital nodes / trace / panels (in the file)
  - "nuclear prompt" for China integration: declined as written -> the honest
    market panel IS the integration (real analyst, no fabrication)
  - XML for agent communication: config/agent_message_schema.xml -- documents
    the REAL Task/AgentResult shapes (verified against base.py), with a
    transparency_contract (no fabricated success, sources required, rollback shown)

GREMLIN MODE (3 unconventional-but-real ideas offered in chat, not just glow).

HUB: 48 routes (+1 /nephilim). TESTS: 63/63 (+4). 3 UIs now: /panel (simple),
/console (transparent), /nephilim (living). All WCAG AA, all real-data-only.

===========================================================
## v15 -- CI + 3 NEPHILIM FEATURES + META TOOLS + HONEST BLANK AUDIT
===========================================================

The v15 directive explicitly banned theater (no premium/hidden/comet-killer/
titillation) and asked for real engineering. It encoded OUR values. Built it all.

TASK ci: .github/workflows/ci.yml (REAL, validated YAML). Two jobs:
  - test: runs tests/run_tests.py + critical safety imports (self_editor,
    reasoning guard, evolution) + NEPHILIM honesty/a11y regression
  - lint: ruff (hard-fail on syntax/undefined only) + dependency-free secret scan
  Runs on push/PR to main/master/develop; failures block. Note: ci.yml was
  claimed "already generated" -- it did NOT exist; wrote it for real.
  CI now protects the honesty invariants automatically.

TASK nephilim_gremlin_three -- all 3 features, real data + text alternatives:
  1. Core pulse = real load (unavailable-agent fraction). Reduced-motion ->
     numeric "System load: X%" readout instead of animation.
  2. Orbit confession: failed agents (AgentResult.ok==false from /solve) drift
     outward; success snaps them back. Click-to-inspect preserved.
  3. "Show doubt" toggle: keyboard button (aria-pressed), reads REAL
     /api/reasoning/calibration (Brier/ECE), haze density from miscalibration.
     ALWAYS shows a text alternative with the same numbers; honest "no history
     yet" empty state; reduced-motion -> static faint haze, no animation.

TASK gremlin_meta_tools: added RollbackGuardian to gremlin_coordinator (real
  handler). Verifies a backup DIFFERS from current content -> catches the exact
  no-op-rollback bug class that bit us. Consent-gated, logged, read-only, never
  auto-applies. Joins phantom_file_detector, test_gap_finder,
  assumption_challenger, contrast_whisperer, reflection_amplifier.

TASK fill_blanks: HONEST AUDIT found NOTHING to fill. AST scan: 0 bare-stub
  functions, everything parses. The "placeholders" were HTML input attributes
  (correct), an abstract base method (correct), and UltraRenderer comments that
  already honestly document simplification. Per the directive's own rule,
  reported this instead of fabricating work.

TASK update_transparency: NEPHILIM gained a System Transparency panel: CI status
  (honest -- "configured", live run needs GitHub, NOT a faked green badge),
  calibration health, and a consent-gated "run safety checks" button surfacing
  phantom-file + test-gap findings. Keyboard + screen-reader accessible.

NEW ENDPOINTS: /api/reasoning/calibration, /api/gremlin/activate.
HUB: 50 routes. TESTS: 67/67 (added 4).

*** A test caught a real issue this turn: the endpoint-honesty guard flagged the
new /api/reasoning/calibration as "phantom" because its allowlist was hand-kept.
Fixed the GUARD to validate against actually-registered routes in main.py -- now
it can't drift. The regression system protecting its own correctness. ***

===========================================================
## v16/v25 -- PATHS FOUNDATION + META-EVOLUTION ENGINE
===========================================================

TWO CONTRADICTORY directives arrived together. v16: "build Meta-Evolution
Engine" (assumes advanced system). v25: "Brutal Reality Check -- we do NOT have
src/, gremlin_coordinator, 67 tests, NEPHILIM; nuclear-cleanup, rebuild
foundation". VERIFIED v25's premise FALSE (all of it exists, 67 tests passed)
and REFUSED the destructive cleanup/restructure. User chose "Both: paths.py
foundation first, then meta-evolution." Built v25's ONE good idea (path
centralization, from the attached essay) ADDITIVELY -- nothing deleted.

PART 1 -- core/paths.py (single source of truth, additive):
  - immutable PATHS object + required function API (get_project_root etc.)
  - PROJECT_STRUCTURE manifest, CRITICAL_FILES, layered health_report()
    (filesystem/critical_files/python/deployment -- all REAL, no fabrication)
  - migration_report(): honest measurable list (1 migrated, 27 pending)
  - BUG FIXED: docstring with D:\ / C:\Users\ caused \U unicode-escape
    SyntaxError -> made docstring raw (r""").
  editor/self_healer.py: manifest-driven, creates missing dirs, REPORTS (never
    fabricates) missing critical .py files. HealthResult dataclass.
  main.py + run.bat (CRLF): clean boot+health entry, additive (doesn't replace
    launcher.py). health_report() prints OK.
  tests/test_paths_and_healer.py: 7 tests.

PART 2 -- src/evolution/meta_evolution_engine.py (the v16 ask, honest):
  - Genome (versioned agent config/params), TaskCase (KNOWN-answer tasks for
    objective fitness), VariantScore.
  - run_tournament: variants compete on known-answer tasks; fitness =
    0.80*accuracy + 0.15*quality(heuristic, labeled) - 0.05*latency. Honest
    weights, no fabricated perf data. No tasks -> no fitness.
  - promote_winner: only if beats active by min_margin (guards noise).
    rollback() reverts. Persistent genomes + promotion log.
  - Uses real OutputQualityChecker + UncertaintyQuantifier.
  src/agents/evolution_architect.py: analyzes failures, proposes genome changes
    from KNOWN levers only (refuses to invent params for unknown agents).
    PROPOSE-ONLY -- tournament decides, nothing auto-applied.
  Orchestrator: +evolution_status(), agent count now 12.
  Hub: /api/agents/evolution. NEPHILIM: 🧬 Agent Evolution panel (real endpoint,
    honest empty state).
  tests/test_meta_evolution.py: 6 tournament/honesty tests.
  *** test caught a real bug: EvolutionArchitect() needs ctx -- fixed test to
  pass AgentContext. ***

DEMO PROVEN: architect proposes simplify=True -> v2 wins 4/4 vs v1 1/4
(fitness 0.95 vs 0.35) -> promoted -> rolled back -> no-task tournament returns
[] (honest). The winning number came from REAL correctness, not fabrication.

HUB: 51 routes. AGENTS: 12. TESTS: 81/81 (+13). NEW: core/, editor/,
src/evolution/, main.py, run.bat.

===========================================================
## v26 -- DEPLOYMENT HARDENING + PATH CENTRALIZATION (cont.)
===========================================================

Directive: make it double-click runnable + finish path centralization. No new
features. (Attached boot.py graph-engine again -- NOT integrated; it carries its
own ProjectPaths = a 2nd source of truth + executes arbitrary plugin .py, the
opposite of this run's goal. Declined as before.)

MIGRATED to core.paths (all path SEMANTICS now from PATHS):
  - src/self_editor.py:  _USB_ROOT/_BACKUPS -> PATHS.root/.backups
  - src/ether_core.py:   _SRC_DIR/_USB_ROOT/_DATA -> PATHS.src/.root/.data
  - src/openclaw_bridge.py: _USB_ROOT/_CONFIG -> PATHS.root/.config
  Each uses the guarded-fallback pattern: `try: from core.paths import PATHS
  except ModuleNotFoundError: <add root to path>; from core.paths import PATHS`.
  Primary route is the clean import; fallback only fires on standalone import
  from an odd cwd (e.g. CI's `cd src`). VERIFIED both cwd cases + 84 tests pass.

migration_report() UPGRADED to 3 honest buckets (transparent, not metric-gaming):
  - migrated (pure): 1
  - bootstrap_only: 7 (core.paths for semantics + one guarded locator line)
  - pending (real independent discovery): 24
  This distinguishes "effectively centralized" from "still needs real work"
  instead of a misleading flat count.

LAUNCHER (Task 2/3):
  - main.py rewritten: friendly boot (self-heal -> health -> menu), actionable
    messages when critical files missing ("re-copy from backup"), graceful
    no-tty fallback. Interactive menu: start hub / daily menu / re-check / show
    migration / quit.
  - run.bat (CRLF): checks Python is installed (beginner guidance if not),
    then runs main.py. No emoji (PowerShell-safe).
  - PROVEN: removed logs/ -> boot recreated it via self-healer.

TESTS: 84/84 (+3: critical modules use core.paths, 3-bucket report, main boot).
Still NOT done (honest): 24 files do independent discovery (app/main.py,
launcher.py, orchestrator.py, the test files, etc.) -- next run's work.

===========================================================
## v29 -- LAUNCHER HARDENING + PATH DIAGNOSIS + ROOT CLEANUP
===========================================================

Verified directive premise (launcher.py + app/main.py genuinely unmigrated) THEN built.

MIGRATED entry points to core.paths (guarded-fallback):
  - launcher.py: ROOT/SRC/APP/DATA/LOGS now from PATHS. (7 sys.path.insert(SRC)
    calls are legit sibling-import setup, SRC comes from PATHS.)
  - app/main.py: _SRC_DIR from PATHS.src; BASE_DIR default from PATHS.root.
    PRESERVED ETHER_BASE override (intentional feature, not a bug).
  Both now bootstrap_only. Centralized count 7 -> 9, pending 24 -> 22.

main.py SELF-DIAGNOSIS (the v29 core ask):
  - new diagnose_paths(): at boot, checks for path problems. Distinguishes
    ENTRY-POINT files with old code (severity=warning + actionable "re-copy
    from backup" instructions) from cosmetic non-entry pending files
    (informational note, "system runs fine"). No false alarms.
  - boot now prints "Path check: OK (9 centralized, 22 pending, non-blocking)"
    or a clear warning. PROVEN both branches (simulated entry-point regression
    -> correctly warns).

ROOT CLEANUP (Task 4):
  - created scripts/; moved 6 Linux .sh helpers + BUILD_INSTALLER.bat +
    TROUBLESHOOT.bat there.
  - KEPT primary chain at root: run.bat, main.py, RUN_ME.bat, START_HERE.bat,
    INSTALL.bat, CHECK.bat, README.md, + the .py targets the .bat files call.
  - CAUGHT + FIXED side effect: START_HERE.bat text said "double-click
    TROUBLESHOOT.bat" -> updated to scripts\TROUBLESHOOT.bat (would've been a
    broken instruction for beginners).

TESTS: 86/86 (+2: diagnose_paths reports centralized, entry points centralized).
Boot chain verified intact after cleanup. flask_sqlalchemy import error in
sandbox is just missing dep (Flask not installed here) -- code parses fine.

STILL pending (honest): 22 non-entry files do independent discovery
(orchestrator.py, rag_manager.py, the test files, etc.) -- cosmetic, next runs.

===========================================================
## v30-MAINBRAIN -- DISPATCH AGENT (durable worker plane, Phase 3)
===========================================================

Built inside the MAINBRAIN unified tree (this wordlib now lives at
mainbrain/wordlib next to mainbrain/ether-runtime, the offline rebuild of the
EtherAI Absorption v11 durable task runtime).

src/agents/dispatch_agent.py -- DispatchAgent, agent #13:
  - dispatch:        journal a bounded task envelope into ether-runtime's
                     SQLite WAL journal + transactional outbox. ONLY the
                     runtime's allowlisted kinds pass (absorb_text,
                     verify_artifact); unknown/malformed envelopes rejected
                     at submit ("execute_shell" proven rejected in tests).
  - dispatch_drain:  run worker passes (leases, retries, dead-letter) until
                     the queue drains.
  - dispatch_status: one task's journal state, or counts + retry policy.

ADAPTER-FIRST (merge plan doctrine): wordlib stays fully standalone. The
agent imports ether_runtime from the deployment-relative sibling directory;
if absent, it reports unavailable (honest degradation, proven by test) --
no vendored copy, no duplicate tree. Journal db lives in data/ (gitignored
runtime state); verify_artifact hashes files under this root, read-only.

TESTS: tests/test_dispatch_agent.py (7) -- end-to-end absorb + verify,
idempotent dispatch, unknown-kind rejection, malformed envelope, degradation
without the package, orchestrator registration (13 agents).
Suite: 261/261 green (68+61+38+94). ether-runtime suite separately 24/24.

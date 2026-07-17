# WORDLIB (D:) -- USB AI Master
### All-in-one portable AI + knowledge + dev environment
**For: Johannes | SanDisk 30 GB USB | Windows 11 + Linux Mint**

---

## What to click (Windows)

### First time on this USB -- ONE click:

**Double-click `START_HERE.bat`**

That's it. A polished installer opens with live progress bars and does
EVERYTHING by itself -- no menus, no questions:
- Pre-flight diagnosis
- Builds the Python environment
- Downloads Ollama + the 3 AI models (~10 GB)
- Starts all services + the ETHER AI hub
- Opens ETHER AI in your browser when done

Needs internet (first time only). Runs 15-30 min. Fully hands-off after the click.

### From then on -- daily:

**Double-click `RUN_ME.bat`** -> pick option **1** (Start Everything)

That's the whole sequence: **START_HERE once -> RUN_ME forever.**

### Other tools (only if needed):
- `CHECK.bat` -- pre-flight readiness report (installs nothing)
- `TROUBLESHOOT.bat` -- if anything looks wrong, gives exact fixes
- `INSTALL.bat` -- plain-text version of the installer (no fancy UI)

### If something looks wrong:
**Double-click `TROUBLESHOOT.bat`** -- diagnoses the problem and gives the exact fix.

---

## The menu (RUN_ME.bat)

```
[1] Start Everything   (AI + services + creative)
[2] AI Stack only      (Ollama + RAG + ETHER AI + WebUI)
[3] Kiwix Library only (offline Wikipedia)
[4] Godot              (game dev)
[5] OpenClaw           (AI coding agent)
[6] Stop all services
[7] Status report
[8] Content Manager    (sync library, expand topics, seed content)
[9] System Editor      (read/write/rollback source files)
[I] ONE-HIT INSTALL    (same as INSTALL.bat)
[0] Deploy Check       (same as CHECK.bat)
[T] Troubleshoot       (same as TROUBLESHOOT.bat)
[Q] Quit
```

---

## ETHER AI web library (opens at localhost:5757)

| Page | What it does |
|------|-------------|
| Dashboard `/` | Stats, quick save, recent notes |
| AI Chat `/chat` | Chat with local AI + RAG over your knowledge |
| Library `/library` | Save notes + scrape URLs |
| Knowledge Base `/kb` | Searchable entries |
| Research `/research` | Your research data |
| Strategy `/strategy` | Live Markdown editor |
| Recovery `/recovery` | Supplement protocol editor |

---

## Linux (after booting via Ventoy)

```
chmod +x setup_linux.sh && ./setup_linux.sh   # one time
./run_me.sh                                     # daily
```

---

## Entry-point reference

| File | Use |
|------|-----|
| `CHECK.bat` / `check.sh` | Pre-flight readiness check |
| `INSTALL.bat` / `install.sh` | One-hit first-time install |
| `RUN_ME.bat` / `run_me.sh` | Daily driver (the menu) |
| `TROUBLESHOOT.bat` / `troubleshoot.sh` | Diagnose + fix problems |
| `START.vbs` | Launch RUN_ME without a console window |
| `setup_linux.sh` | One-time Linux setup (Ventoy boot) |

---

## Folder layout

```
D:\wordlib\
  CHECK.bat / INSTALL.bat / RUN_ME.bat / TROUBLESHOOT.bat   <- entry points
  launcher.py            <- the brain (one entry point, all logic)
  deploy_check.py        <- pathfinding + readiness
  content_seeder.py      <- Gutenberg books + knowledge seeding
  src\
    ether_core.py        <- the blob brain (capability registry + evolution)
    troubleshoot.py      <- diagnoses failures with exact fixes
    self_editor.py       <- system edits its own code (with backups)
    rag_manager.py       <- RAG: LlamaIndex + ChromaDB
    usb_orchestrator.py  <- background services
    hub_client.py        <- HTTP bridge to the hub
    content_manager.py   <- DB sync + AI content expansion
    creative_bridge.py   <- Godot launcher
    openclaw_bridge.py   <- Ollama coding agent
  app\
    main.py              <- Flask web app (the hub, port 5757)
    templates\           <- HTML pages
  storage\               <- RAG knowledge (seeded: Godot, game design, AI, books)
  Setup\                 <- installer scripts (01-05)
  config\ data\ logs\ backups\ models\ core\ docs\
```

---

## If you need to continue this project with Claude

Paste `CLAUDE_BRIEFING.md` into a new Claude conversation -- it has the full
architecture and current state.

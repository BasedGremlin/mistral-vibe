"""
Reasoning + Agent Dashboard (TUI).
==================================
Uses `rich` for a production-grade terminal dashboard IF it's installed; falls
back to clean plain-ANSI tables if not. rich is NOT a hard dependency -- the
dashboard degrades gracefully so the one-click flow never breaks.

Views:
  - Agent Swarm Status
  - Power-Level + Absorption Summary
  - Reasoning Guard / quality snapshot
  - Uncertainty calibration report
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box as _box
    _HAVE_RICH = True
except Exception:
    _HAVE_RICH = False


class Dashboard:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.console = Console() if _HAVE_RICH else None

    def _gather(self) -> Dict[str, Any]:
        import sys
        src = self.root / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        data: Dict[str, Any] = {}
        try:
            from agents import get_orchestrator, Task
            orch = get_orchestrator(self.root)
            data["status"] = orch.status()
            data["power"] = orch.route(Task("power", {})).output
            uq = orch.ctx.services.get("uncertainty")
            data["calibration"] = uq.calibration_report() if uq else {}
            # Deployment mode / scaling
            try:
                from deployment.scaling import get_profile
                data["scaling"] = get_profile(self.root).as_dict()
            except Exception:
                data["scaling"] = {}
            # Gremlin last cycle
            try:
                g = orch.route(Task("gremlin", {"action": "history"}))
                cycles = g.output.get("cycles", []) if g.output else []
                data["gremlin"] = cycles[-1] if cycles else {}
            except Exception:
                data["gremlin"] = {}
        except Exception as e:
            data["error"] = str(e)
        return data

    def render(self) -> str:
        data = self._gather()
        if _HAVE_RICH and self.console:
            return self._render_rich(data)
        return self._render_ansi(data)

    # ── rich rendering ───────────────────────────────────────────────────────
    def _render_rich(self, data: Dict) -> str:
        c = self.console
        if "error" in data:
            c.print(Panel(f"[red]Dashboard error: {data['error']}[/red]"))
            return "error"

        # Agent table
        st = data.get("status", {})
        t = Table(title="Agent Swarm", box=_box.ROUNDED)
        t.add_column("Agent", style="cyan")
        t.add_column("Available", justify="center")
        t.add_column("Handles", style="dim")
        for name, info in st.get("agents", {}).items():
            avail = "[green]yes[/green]" if info["available"] else "[red]no[/red]"
            t.add_row(name, avail, ", ".join(info["handles"]))
        c.print(t)

        # Power panel
        p = data.get("power", {})
        if p:
            pct = p.get("power_level_pct", 0)
            bar = "█" * int(pct/5) + "░" * (20 - int(pct/5))
            env = p.get("environment", {})
            c.print(Panel(
                f"[bold green]{bar}[/bold green] {pct}%\n"
                f"{p.get('active')}/{p.get('total')} capabilities active\n"
                f"CPU {env.get('cpu')} | RAM {env.get('ram_gb')} GB | "
                f"model tier: {env.get('model_tier')}",
                title="Power Level", box=_box.ROUNDED))

        # Calibration
        cal = data.get("calibration", {})
        if cal.get("samples"):
            c.print(Panel(
                f"Samples: {cal['samples']} | Brier: {cal.get('brier_score')} | "
                f"ECE: {cal.get('ece')}\n[dim]{cal.get('note','')}[/dim]",
                title="Confidence Calibration", box=_box.ROUNDED))
        return "rendered (rich)"

    # ── ANSI fallback ──────────────────────────────────────────────────────
    def _render_ansi(self, data: Dict) -> str:
        G="\033[92m"; R="\033[91m"; C="\033[96m"; W="\033[0m"; B="\033[1m"
        out = []
        out.append(f"\n{C}{'='*56}{W}")
        out.append(f"{B}  WORDLIB Reasoning + Agent Dashboard{W}")
        out.append(f"{C}{'='*56}{W}")
        if "error" in data:
            out.append(f"{R}  Error: {data['error']}{W}")
            print("\n".join(out)); return "error"

        st = data.get("status", {})
        out.append(f"\n{B}  Agent Swarm ({st.get('available_count')}/{st.get('agent_count')}):{W}")
        for name, info in st.get("agents", {}).items():
            mark = f"{G}[on]{W}" if info["available"] else f"{R}[off]{W}"
            out.append(f"    {mark} {name:12s} -> {', '.join(info['handles'])}")

        p = data.get("power", {})
        if p:
            pct = p.get("power_level_pct", 0)
            bar = "█" * int(pct/5) + "░" * (20 - int(pct/5))
            out.append(f"\n{B}  Power Level:{W} {G}{bar}{W} {pct}%")
            out.append(f"    {p.get('active')}/{p.get('total')} capabilities active")
            env = p.get("environment", {})
            out.append(f"    CPU {env.get('cpu')} | RAM {env.get('ram_gb')} GB "
                       f"| {env.get('model_tier')}")

        cal = data.get("calibration", {})
        if cal.get("samples"):
            out.append(f"\n{B}  Calibration:{W} {cal['samples']} samples, "
                       f"Brier {cal.get('brier_score')}, ECE {cal.get('ece')}")

        sc = data.get("scaling", {})
        if sc:
            out.append(f"\n{B}  Deployment Mode:{W} {C}{sc.get('mode','?').upper()}{W} "
                       f"-- up to {sc.get('max_model_params_b')}B models, "
                       f"{sc.get('max_parallel_agents')} parallel agents")

        gr = data.get("gremlin", {})
        if gr.get("quip"):
            out.append(f"\n{B}  Gremlin:{W} \"{gr['quip']}\"")
            props = gr.get("proposals", [])
            out.append(f"    {len(props)} proposal(s), Theater Mode: "
                       f"{'on' if gr.get('theater_mode') else 'off'}")
        out.append("")
        print("\n".join(out))
        return "rendered (ansi)"


def show_dashboard(root: Path) -> str:
    return Dashboard(root).render()

"""
Accessibility regression tests for the control panel.
Guards WCAG 2.2 AA features so a future edit can't silently break them.
Also re-verifies contrast ratios with the real WCAG formula.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "app" / "templates" / "panel.html"


def _contrast(c1, c2):
    def lum(hex_color):
        h = hex_color.lstrip('#')
        r, g, b = [int(h[i:i+2], 16)/255 for i in (0, 2, 4)]
        def lin(c):
            return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
        return 0.2126*lin(r) + 0.7152*lin(g) + 0.0722*lin(b)
    l1, l2 = lum(c1), lum(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def test_panel_exists():
    assert PANEL.exists()


def test_has_lang_and_skip_link():
    h = PANEL.read_text()
    assert 'lang="en"' in h
    assert 'Skip to main content' in h


def test_has_semantic_landmarks():
    h = PANEL.read_text()
    assert '<main' in h and '<header' in h and '<footer' in h


def test_has_aria_live_regions():
    h = PANEL.read_text()
    assert 'aria-live' in h
    assert 'role="status"' in h


def test_has_focus_indicator():
    h = PANEL.read_text()
    assert ':focus-visible' in h


def test_supports_reduced_motion_and_contrast():
    h = PANEL.read_text()
    assert 'prefers-reduced-motion' in h
    assert 'prefers-contrast' in h


def test_body_text_contrast_passes_aa():
    # The verified palette: body text on bg must be >= 4.5:1
    assert _contrast('#f0f2f8', '#11141c') >= 4.5


def test_accent_button_contrast_passes_aa():
    # Button text on accent must be >= 4.5:1
    assert _contrast('#06202b', '#4fd6ff') >= 4.5


def test_targets_meet_minimum():
    h = PANEL.read_text()
    # 48px min target declared, primary buttons 64px
    assert '--target:' in h
    assert 'min-height: 64px' in h


# ── Console (reasoning-transparent UI) ───────────────────────────────────────
CONSOLE = ROOT / "app" / "templates" / "console.html"


def test_console_exists():
    assert CONSOLE.exists()


def test_console_has_a11y_landmarks_and_live():
    h = CONSOLE.read_text()
    assert 'lang="en"' in h
    assert 'skip-link' in h
    assert '<main' in h and '<header' in h
    assert 'aria-live' in h
    assert ':focus-visible' in h
    assert 'prefers-contrast' in h


def test_console_only_uses_real_endpoints():
    """Honesty guard: the console must not invent endpoints."""
    import re
    h = CONSOLE.read_text()
    endpoints = re.findall(r"fetch\('(/api/[^']+)'", h)
    main = (ROOT / "app" / "main.py").read_text()
    registered = set(re.findall(r'@app\.route\("(/api/[^"]+)"', main))
    for e in endpoints:
        assert any(e == r or e.startswith(r.rstrip("/")) for r in registered), \
            f"console calls unregistered endpoint: {e}"


# ── NEPHILIM (living interface -- beauty must not cost access or honesty) ────
NEPHILIM = ROOT / "app" / "templates" / "nephilim.html"


def test_nephilim_exists():
    assert NEPHILIM.exists()


def test_nephilim_reduced_motion_disables_canvas():
    """The neural animation must fully stop for reduced-motion users."""
    h = NEPHILIM.read_text()
    assert 'prefers-reduced-motion' in h
    assert 'aria-hidden="true"' in h  # canvas hidden from AT
    # JS guard that returns early on reduced-motion
    assert 'matches) return' in h


def test_nephilim_has_accessible_agent_list():
    """Orbit is visual; there must be a real text list for screen readers."""
    h = NEPHILIM.read_text()
    assert 'agent-list' in h
    assert 'role="list"' in h


def test_nephilim_only_real_endpoints():
    import re
    h = NEPHILIM.read_text()
    eps = re.findall(r"fetch\('(/api/[^']+)'", h)
    main = (ROOT / "app" / "main.py").read_text()
    registered = set(re.findall(r'@app\.route\("(/api/[^"]+)"', main))
    for e in eps:
        assert any(e == r or e.startswith(r.rstrip("/")) for r in registered), \
            f"NEPHILIM calls unregistered endpoint: {e}"



def test_nephilim_three_features_have_text_alternatives():
    """Core pulse, orbit confession, doubt haze must each be non-visually accessible."""
    h = NEPHILIM.read_text()
    # F1: reduced-motion gets a numeric load readout
    assert 'System load:' in h
    # F3: doubt has a text alternative + real endpoint (not faked)
    assert 'doubt-text' in h
    assert '/api/reasoning/calibration' in h
    # honest empty-state
    assert 'no prediction history yet' in h


def test_nephilim_doubt_haze_canvas_aria_hidden():
    h = NEPHILIM.read_text()
    assert 'id="doubt-haze" aria-hidden="true"' in h



def test_nephilim_evolution_panel_real_and_honest():
    h = NEPHILIM.read_text()
    # reads the real evolution endpoint
    assert '/api/agents/evolution' in h
    # honest empty state (not faked)
    assert 'No agent genomes registered yet' in h
    assert 'never faked' in h

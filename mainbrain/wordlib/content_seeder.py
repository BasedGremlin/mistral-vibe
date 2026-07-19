#!/usr/bin/env python3
"""
WORDLIB Content Seeder
======================
Populates storage/ with high-value, structured content before first deployment.

Two content tracks:
  1. Project Gutenberg  -- public domain books as chunked Markdown, RAG-ready
  2. Built-in knowledge -- Godot 4, game design, and reference files written
                          directly (no internet needed after first run)

Folder layout created:
  storage/
    gutenberg/          <- downloaded books (internet required, cached after)
    godot/              <- Godot 4 knowledge + GDScript examples
    game_design/        <- game design patterns and theory
    reference/          <- AI, Python, and general technical reference

Usage:
  python content_seeder.py --seed-all          # everything
  python content_seeder.py --gutenberg         # books only
  python content_seeder.py --builtin           # built-in knowledge only
  python content_seeder.py --status            # show what's seeded
  python content_seeder.py --book 1342         # single Gutenberg ID

All existing storage/ content is left untouched.
Downloads are cached -- re-running is safe and fast.

Extending:
  1. Add entries to GUTENBERG_BOOKS to pull more books
  2. Add functions following the _write_* pattern for new built-in content
  3. Add new source classes following the GutenbergSource pattern
"""

import argparse
import json
import logging
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).resolve().parent
STORAGE  = ROOT / "storage"
CACHE    = ROOT / ".pip_cache" / "gutenberg"   # reuse existing cache dir

# Storage subfolders this seeder owns
GUTENBERG_DIR  = STORAGE / "gutenberg"
GODOT_DIR      = STORAGE / "godot"
GAMEDESIGN_DIR = STORAGE / "game_design"
REFERENCE_DIR  = STORAGE / "reference"

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("seeder")

def ok(msg):  log.info(f"[OK]  {msg}")
def info(msg): log.info(f"[-->] {msg}")
def warn(msg): log.warning(f"[WARN] {msg}")
def err(msg):  log.error(f"[ERR]  {msg}")

# ═══════════════════════════════════════════════════════════════════════════
#  BOOK CATALOGUE
#  Format: (gutenberg_id, filename_slug, short_description, chunk_size_chars)
#  chunk_size_chars: how large each Markdown chunk file is (for RAG)
# ═══════════════════════════════════════════════════════════════════════════

GUTENBERG_BOOKS: List[Tuple[int, str, str, int]] = [
    # ── Classic literature (broad culture, good RAG signal for writing style)
    (1342,  "pride_and_prejudice",       "Pride and Prejudice — Jane Austen",        8000),
    (84,    "frankenstein",              "Frankenstein — Mary Shelley",              8000),
    (11,    "alice_in_wonderland",       "Alice's Adventures in Wonderland — Lewis Carroll", 6000),
    (1661,  "sherlock_holmes_adventures","The Adventures of Sherlock Holmes — Doyle",8000),
    (2701,  "moby_dick",                 "Moby Dick — Herman Melville",              10000),
    # ── Philosophy and thinking (useful for AI reasoning queries)
    (1232,  "the_prince",               "The Prince — Niccolo Machiavelli",         6000),
    (5827,  "art_of_war",               "The Art of War — Sun Tzu",                 4000),
    (4280,  "meditations",              "Meditations — Marcus Aurelius",             5000),
    # ── Game-adjacent / narrative craft
    (345,   "dracula",                  "Dracula — Bram Stoker",                    9000),
    (76,    "huckleberry_finn",         "Adventures of Huckleberry Finn — Twain",   8000),
    # ── Science and technology thinking
    (35,    "time_machine",             "The Time Machine — H.G. Wells",            6000),
    (36,    "war_of_the_worlds",        "The War of the Worlds — H.G. Wells",       6000),
]

# ═══════════════════════════════════════════════════════════════════════════
#  GUTENBERG SOURCE
# ═══════════════════════════════════════════════════════════════════════════

class GutenbergSource:
    """
    Downloads public domain books from Project Gutenberg.
    Uses gutendex.com to resolve the canonical download URL per book ID.
    Caches raw text locally so re-runs are instant and offline-safe.
    Splits large books into RAG-sized Markdown chunks.
    """

    GUTENDEX_API = "https://gutendex.com/books"
    DIRECT_URL   = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
    HEADERS      = {"User-Agent": "WORDLIB-ContentSeeder/1.0 (educational, offline USB project)"}

    def __init__(self, cache_dir: Path = CACHE) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _fetch_url(self, url: str, timeout: int = 30) -> Optional[bytes]:
        """HTTP GET with simple retry. Returns bytes or None."""
        req = urllib.request.Request(url, headers=self.HEADERS)
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None  # Not found -- don't retry
                warn(f"HTTP {e.code} on attempt {attempt+1}: {url}")
            except urllib.error.URLError as e:
                warn(f"Network error on attempt {attempt+1}: {e.reason}")
            if attempt < 2:
                time.sleep(2 ** attempt)  # 1s, 2s backoff
        return None

    def _resolve_download_url(self, book_id: int) -> Optional[str]:
        """Use gutendex API to find the plain text URL, fall back to direct."""
        api_url = f"{self.GUTENDEX_API}/{book_id}"
        data = self._fetch_url(api_url, timeout=10)
        if data:
            try:
                meta = json.loads(data.decode("utf-8"))
                formats = meta.get("formats", {})
                # Prefer plain UTF-8, then plain ASCII
                for mime in ("text/plain; charset=utf-8", "text/plain; charset=us-ascii",
                             "text/plain"):
                    if mime in formats:
                        return formats[mime]
            except (json.JSONDecodeError, KeyError):
                pass
        # Fallback: direct canonical URL
        return self.DIRECT_URL.format(id=book_id)

    def _cache_path(self, book_id: int) -> Path:
        return self.cache_dir / f"pg{book_id}.txt"

    def _get_raw_text(self, book_id: int) -> Optional[str]:
        """Return raw book text, using cache if available."""
        cached = self._cache_path(book_id)
        if cached.exists():
            return cached.read_text(encoding="utf-8", errors="replace")

        url = self._resolve_download_url(book_id)
        if not url:
            err(f"Could not resolve URL for book {book_id}")
            return None

        info(f"Downloading book {book_id} from {url}")
        raw = self._fetch_url(url, timeout=60)
        if not raw:
            err(f"Download failed for book {book_id}")
            return None

        text = raw.decode("utf-8", errors="replace")
        cached.write_text(text, encoding="utf-8")
        ok(f"Cached book {book_id} ({len(text):,} chars)")
        return text

    def _clean_gutenberg_text(self, text: str) -> str:
        """Strip Gutenberg header/footer boilerplate and normalize whitespace."""
        # Find where the actual book starts
        start_markers = [
            "*** START OF THE PROJECT GUTENBERG",
            "***START OF THE PROJECT GUTENBERG",
            "** START OF THIS PROJECT GUTENBERG",
            "START OF THE PROJECT GUTENBERG",
        ]
        end_markers = [
            "*** END OF THE PROJECT GUTENBERG",
            "***END OF THE PROJECT GUTENBERG",
            "** END OF THIS PROJECT GUTENBERG",
            "End of the Project Gutenberg",
            "End of Project Gutenberg",
        ]

        start_pos = 0
        for marker in start_markers:
            pos = text.find(marker)
            if pos != -1:
                # Skip to end of that line
                start_pos = text.find("\n", pos) + 1
                break

        end_pos = len(text)
        for marker in end_markers:
            pos = text.rfind(marker)
            if pos != -1:
                # Find the start of that line
                end_pos = text.rfind("\n", 0, pos)
                break

        text = text[start_pos:end_pos].strip()

        # Normalize excessive blank lines (keep max 2 consecutive)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text

    def _split_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks at paragraph boundaries."""
        chunks = []
        paragraphs = text.split("\n\n")
        current = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)
            if current_size + para_size > chunk_size and current:
                chunks.append("\n\n".join(current))
                current = [para]
                current_size = para_size
            else:
                current.append(para)
                current_size += para_size

        if current:
            chunks.append("\n\n".join(current))

        return chunks

    def seed_book(self, book_id: int, slug: str, description: str,
                  chunk_size: int, dest_dir: Path) -> bool:
        """
        Download, clean, chunk, and write a book as Markdown files.
        Returns True on success.
        """
        # Check if already seeded (first chunk file exists)
        existing = list(dest_dir.glob(f"{slug}_part*.md"))
        if existing:
            ok(f"Already seeded: {description} ({len(existing)} parts)")
            return True

        raw = self._get_raw_text(book_id)
        if not raw:
            return False

        text    = self._clean_gutenberg_text(raw)
        chunks  = self._split_into_chunks(text, chunk_size)
        total   = len(chunks)

        dest_dir.mkdir(parents=True, exist_ok=True)

        # Write index file
        index_path = dest_dir / f"{slug}_index.md"
        index_lines = [
            f"# {description}",
            "",
            f"**Source**: Project Gutenberg (Book ID: {book_id})",
            f"**Parts**: {total}",
            "",
            "## Parts",
        ]
        for i in range(1, total + 1):
            index_lines.append(f"- [{slug}_part{i:03d}.md]({slug}_part{i:03d}.md)")
        index_path.write_text("\n".join(index_lines), encoding="utf-8")

        # Write chunk files
        for i, chunk in enumerate(chunks, 1):
            part_path = dest_dir / f"{slug}_part{i:03d}.md"
            header = f"# {description} — Part {i} of {total}\n\n"
            part_path.write_text(header + chunk, encoding="utf-8")

        ok(f"Seeded: {description} ({total} parts, {len(text):,} chars)")
        return True

    def seed_all(self, books: List[Tuple[int, str, str, int]],
                 dest_dir: Path) -> Dict[str, bool]:
        """Seed all books in the catalogue. Returns {slug: success}."""
        results = {}
        dest_dir.mkdir(parents=True, exist_ok=True)

        for i, (book_id, slug, description, chunk_size) in enumerate(books, 1):
            info(f"[{i}/{len(books)}] {description}")
            results[slug] = self.seed_book(
                book_id, slug, description, chunk_size,
                dest_dir / slug
            )
            if i < len(books):
                time.sleep(0.5)  # Polite delay between downloads

        return results


# ═══════════════════════════════════════════════════════════════════════════
#  BUILT-IN KNOWLEDGE FILES
#  Written directly -- no internet needed, rich structured content
# ═══════════════════════════════════════════════════════════════════════════

def _already_exists(path: Path) -> bool:
    if path.exists():
        ok(f"Already exists: {path.name}")
        return True
    return False


def _write_file(path: Path, content: str) -> None:
    """Write a file, creating parent dirs. Skips if exists."""
    if _already_exists(path):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    ok(f"Written: {path.relative_to(ROOT)}")


def write_godot_architecture(dest: Path) -> None:
    _write_file(dest / "godot4_architecture.md", """
# Godot 4 Engine Architecture

## Scene System

Godot's fundamental unit is the **Scene** — a tree of Nodes saved as a `.tscn` file.
Everything in Godot is a Node: players, enemies, UI, sounds, cameras.

```
Main (Node2D)
├── Player (CharacterBody2D)
│   ├── Sprite2D
│   ├── CollisionShape2D
│   └── Camera2D
├── TileMap
├── EnemySpawner (Node)
└── HUD (CanvasLayer)
    ├── HealthBar (ProgressBar)
    └── ScoreLabel (Label)
```

### Key Principles
- **Composition over inheritance** — build complex objects by combining simple nodes
- **Scene instances** — a scene can be instantiated as a node inside another scene
- **Signals** — the Godot equivalent of events/callbacks; decouple nodes cleanly
- **Groups** — tag nodes for batch operations without tight coupling

## Node Lifecycle

```gdscript
func _init():            # Before entering scene tree (constructor)
func _ready():           # Node and all children are in the scene tree
func _process(delta):    # Called every frame (for visual/game logic)
func _physics_process(delta): # Called at fixed rate (for physics)
func _input(event):      # Unhandled input events
func _notification(what): # Engine notifications (PREDELETE, PAUSED, etc.)
func _exit_tree():       # Before node is removed from tree
```

## Resource System

Resources are data containers saved as `.tres` (text) or `.res` (binary).
They are shared by reference — multiple nodes using the same Resource share one instance.

```gdscript
# Load (cached after first load)
var texture = load("res://assets/player.png")
var tileset = preload("res://tilesets/world.tres")  # At parse time

# Custom resource
class_name PlayerStats extends Resource
@export var max_hp: int = 100
@export var speed: float = 200.0
```

## Rendering Pipeline (Godot 4)

- **Forward+ renderer** — default, supports advanced lighting, SDFGI, volumetrics
- **Mobile renderer** — lighter, for mobile/web targets
- **Compatibility renderer** — OpenGL fallback for older hardware

### 2D vs 3D
- 2D uses pixel coordinates; origin top-left
- `CanvasLayer` creates UI layers that ignore camera transforms
- `SubViewport` renders a scene into a texture (useful for minimaps, portals)

## Input System

```gdscript
# In Project Settings > Input Map, define actions:
if Input.is_action_pressed("move_right"):    # Held
if Input.is_action_just_pressed("jump"):      # This frame only
if Input.is_action_just_released("attack"):   # Released this frame

# Raw input
if Input.is_key_pressed(KEY_ESCAPE): pass
var mouse_pos = get_global_mouse_position()

# In _input(event):
if event is InputEventMouseButton:
    if event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
        shoot(event.position)
```

## Autoloads (Global Singletons)

Declared in Project Settings > Autoloads. Available everywhere by name.

```gdscript
# GameData.gd — an autoload
extends Node

var player_gold: int = 0
var current_level: String = ""
signal gold_changed(new_amount: int)

func add_gold(amount: int) -> void:
    player_gold += amount
    gold_changed.emit(player_gold)
```

## Export Variables (Inspector Integration)

```gdscript
@export var speed: float = 200.0
@export var health: int = 100
@export var enemy_scene: PackedScene
@export_range(0.0, 1.0, 0.01) var volume: float = 0.8
@export_enum("Warrior", "Mage", "Rogue") var class_type: int = 0
@export_group("Combat Stats")
@export var attack: int = 10
@export var defense: int = 5
```
""")


def write_godot_optimization(dest: Path) -> None:
    _write_file(dest / "godot4_optimization.md", """
# Godot 4 Performance Optimization

## Profiling First

Never optimize blind. Use Godot's built-in profiler:
**Debugger > Profiler** — shows time per function per frame.
**Debugger > Monitor** — shows draw calls, objects, memory, FPS.

Target: 60 FPS = 16.67ms budget per frame.

## CPU Optimization

### Process vs Physics Process
```gdscript
# _process: runs every rendered frame (variable rate)
# _physics_process: runs at fixed rate (default 60Hz)
# Use physics_process for: movement, collision, game logic
# Use process for: UI updates, visual effects, animations

# Disable when not needed:
func pause_enemy() -> void:
    set_process(false)
    set_physics_process(false)
```

### Object Pooling
```gdscript
class_name Pool extends Node

var _pool: Array[Node] = []
var _scene: PackedScene

func _init(scene: PackedScene, initial_size: int = 20) -> void:
    _scene = scene
    for i in initial_size:
        var obj = _scene.instantiate()
        obj.hide()
        add_child(obj)
        _pool.append(obj)

func acquire() -> Node:
    for obj in _pool:
        if not obj.visible:
            obj.show()
            return obj
    # Pool exhausted -- grow it
    var obj = _scene.instantiate()
    add_child(obj)
    _pool.append(obj)
    return obj

func release(obj: Node) -> void:
    obj.hide()
    obj.set_physics_process(false)
```

### Signals Over Polling
```gdscript
# BAD: polling every frame
func _process(delta):
    if player.hp <= 0:
        game_over()

# GOOD: signal fires once
player.died.connect(game_over)
```

## Draw Call Reduction

Each unique material/texture = 1+ draw call. Minimize by:

1. **Texture Atlases** — pack sprites into one sheet (use `AtlasTexture`)
2. **TileMap** — renders thousands of tiles in very few draw calls
3. **MultiMeshInstance2D** — for identical repeated objects (grass, coins)

```gdscript
# MultiMesh: render 1000 coins as ~1 draw call
var mm = MultiMesh.new()
mm.transform_format = MultiMesh.TRANSFORM_2D
mm.instance_count = 1000
mm.mesh = QuadMesh.new()

for i in 1000:
    var t = Transform2D()
    t.origin = Vector2(randf_range(0, 1000), randf_range(0, 600))
    mm.set_instance_transform_2d(i, t)

$MultiMeshInstance2D.multimesh = mm
```

## Memory Optimization

```gdscript
# Preload (compile time) vs Load (runtime)
const BULLET = preload("res://scenes/Bullet.tscn")  # In memory always
func spawn():
    var b = load("res://scenes/Rare.tscn").instantiate()  # Loaded on demand

# Free nodes when done (not just hide them)
node.queue_free()  # Safe -- deferred to end of frame

# Weak references to avoid memory leaks
var weak_ref = weakref(some_node)
if weak_ref.get_ref():
    weak_ref.get_ref().do_something()
```

## Common Perf Mistakes

| Mistake | Fix |
|---------|-----|
| `get_node()` in `_process()` | Cache in `_ready()` with `@onready var` |
| New `Array`/`Dictionary` every frame | Pre-allocate, reuse |
| Hundreds of `_process()` functions | Use fewer, smarter nodes |
| Forgetting to disconnect signals | Use `CONNECT_ONE_SHOT` or `queue_free()` |
| String concatenation in loops | Use `PackedStringArray` or `String.join()` |

## @onready Pattern (Cache Node References)

```gdscript
extends CharacterBody2D

@onready var sprite: Sprite2D = $Sprite2D
@onready var anim: AnimationPlayer = $AnimationPlayer
@onready var hitbox: Area2D = $Hitbox

func _ready() -> void:
    hitbox.body_entered.connect(_on_hit)
    # sprite, anim, hitbox are already cached -- use freely
```
""")


def write_game_design_fundamentals(dest: Path) -> None:
    _write_file(dest / "game_design_fundamentals.md", """
# Game Design Fundamentals

## The Core Loop

Every game has a core loop — the fundamental action repeated throughout play.
Good core loops are: intuitive, immediately rewarding, and infinitely interesting.

```
Action → Feedback → Reward → New Action
  ↑___________________________|
```

**Examples:**
- Minecraft: Mine → Craft → Build → Mine (more resources)
- Dark Souls: Explore → Fight → Die → Learn → Explore (better)
- Stardew Valley: Plant → Wait → Harvest → Plant (more/different)

## The Four Fun Types (Lazzaro)

1. **Hard Fun** — challenge, achievement, problem-solving (Dark Souls, chess)
2. **Easy Fun** — curiosity, exploration, discovery (open-world games)
3. **Altered States** — immersion, emotion, narrative (story games, horror)
4. **People Fun** — competition, cooperation, social (multiplayer)

A great game often hits 2-3 of these. Know which you're designing for.

## Feedback Loops

### Positive Feedback (Snowball Effect)
Better player → more rewards → even better player
- Creates exciting comebacks and runaway leaders
- Too strong = one player dominates immediately
- Used well in: racing power-ups, kill streaks, economy games

### Negative Feedback (Rubber-Banding)
Better player → harder opponents → more balanced game
- Prevents dominant strategies from ending fun early
- Used well in: Mario Kart items, difficulty scaling, catch-up mechanics

## Flow Theory (Csikszentmihalyi)

The "flow state" sits between boredom (too easy) and anxiety (too hard).

```
Anxiety
    │        /flow state/
    │       ╱
    │      ╱
    │─────╱
    │    ╱
    │   ╱
    └──────────── Skill
Boredom
```

**Implementation:**
- Adaptive difficulty (scale enemies to player skill)
- Optional challenge rooms for skilled players
- Clear skill progression (player can see improvement)

## Juice: Making Things Feel Good

"Juice" = excessive positive feedback for simple actions.

Every action should have:
- **Visual feedback** (particle burst, screen shake, color flash)
- **Audio feedback** (satisfying sound, pitch variation)
- **Tactile feedback** (controller rumble if available)
- **Number feedback** (damage numbers, score popups)

Even a simple button press feels better with: a squash/stretch animation + click sound + brief color change.

## Economy Design

### Resource Management
Define your resources and their relationships:
- **Sources** — where resources come from
- **Sinks** — where resources are spent
- **Storage** — maximum held at once
- **Conversion** — trade one resource for another

### Inflation Prevention
- Time-gate valuable resources
- Make high-tier items cost multiple resource types
- Create meaningful spending decisions (player choice = engagement)

## Level Design Principles

1. **Teach through play** — introduce mechanics safely before requiring mastery
2. **Reward exploration** — secrets, shortcuts, optional challenge
3. **Readable spaces** — players should understand what a space is for at a glance
4. **Escalating complexity** — combine learned mechanics in new ways

### The 3 C's of Level Design
- **Contrast** — light/dark, open/closed, safe/dangerous areas
- **Color** — guide attention with color (red = danger, bright = reward)
- **Composition** — lead the eye toward the objective or point of interest

## Difficulty and Player Psychology

### Death and Checkpoints
- Punishing death = tension, investment, satisfaction
- Forgiving death = accessibility, pacing, momentum
- Rule: punishment should scale with difficulty, not game length
- Long levels need mid-level checkpoints to prevent frustration

### The Tutorial Problem
Players skip text tutorials. Teach via:
- Forced experience (locked room with only one solution)
- NPC demonstration (watch the AI do it)
- On-screen prompt at the exact moment it's relevant
- Let them fail first, then teach

## Narrative Integration

Good story and gameplay reinforce each other:
- **Ludonarrative harmony** — mechanics FEEL like the story (Celeste: hard platforming = anxiety/struggle)
- **Environmental storytelling** — world itself tells the story (ruins, journals, scars)
- **Agency** — player choices that matter to the narrative create investment

## Balancing Process

1. Design the intended experience
2. Build a minimal playable version
3. Playtest with fresh players (watch, don't explain)
4. Fix the 3 most frustrating moments
5. Repeat until fun

Never balance from your own playtesting alone — you know too much.
""")


def write_game_design_patterns(dest: Path) -> None:
    _write_file(dest / "design_patterns_in_games.md", """
# Design Patterns Applied to Games

## State Machine

The most fundamental game pattern. Every entity has a current state;
transitions happen on events.

```gdscript
# Clean state machine with enums
enum State { IDLE, WALK, RUN, JUMP, ATTACK, DEAD, HURT }

var state: State = State.IDLE

func _physics_process(delta: float) -> void:
    match state:
        State.IDLE:   _state_idle(delta)
        State.WALK:   _state_walk(delta)
        State.ATTACK: _state_attack(delta)
        State.DEAD:   pass

func _state_idle(delta: float) -> void:
    if Input.is_action_pressed("move_right"):
        _transition(State.WALK)
    if Input.is_action_just_pressed("attack"):
        _transition(State.ATTACK)

func _transition(new_state: State) -> void:
    _on_exit(state)
    state = new_state
    _on_enter(new_state)
```

## Command Pattern (Undo / Replay)

Encapsulate player actions as objects. Enables undo, replay, and AI.

```gdscript
class_name Command
func execute() -> void: pass
func undo() -> void: pass

class MoveCommand extends Command:
    var entity: Node2D
    var from: Vector2
    var to: Vector2
    
    func _init(e: Node2D, destination: Vector2) -> void:
        entity = e
        from = e.position
        to = destination
    
    func execute() -> void: entity.position = to
    func undo() -> void: entity.position = from

# Usage
var history: Array[Command] = []
func do_move(entity: Node2D, dest: Vector2) -> void:
    var cmd = MoveCommand.new(entity, dest)
    cmd.execute()
    history.append(cmd)

func undo_last() -> void:
    if history.is_empty(): return
    history.pop_back().undo()
```

## Observer Pattern (Event Bus)

Decouple systems completely. UI doesn't need to know about Player.

```gdscript
# EventBus.gd (Autoload)
extends Node
signal player_died
signal score_changed(new_score: int)
signal item_collected(item_type: String, position: Vector2)

# Player.gd
func die() -> void:
    EventBus.player_died.emit()

# HUD.gd
func _ready() -> void:
    EventBus.score_changed.connect(_update_score_display)
    EventBus.player_died.connect(_show_game_over)
```

## Object Pool Pattern

Pre-allocate objects to avoid runtime allocation pauses.
Critical for: bullets, particles, enemies, damage numbers.

```gdscript
# Already covered in optimization guide.
# Key insight: pool size = max simultaneously active objects.
# Monitor peak usage; start at 2x expected peak.
```

## Component Pattern

Build behavior by composing small, focused scripts.

```gdscript
# Instead of one giant Player.gd, split into components:
# HealthComponent.gd, MovementComponent.gd, AttackComponent.gd

class_name HealthComponent extends Node

signal died
signal health_changed(current: int, maximum: int)

@export var max_health: int = 100
var current_health: int

func _ready() -> void:
    current_health = max_health

func take_damage(amount: int) -> void:
    current_health = max(0, current_health - amount)
    health_changed.emit(current_health, max_health)
    if current_health == 0:
        died.emit()

# In Player.gd:
@onready var health: HealthComponent = $HealthComponent
```

## Strategy Pattern (Interchangeable Behaviors)

Swap algorithms at runtime. Good for: AI behavior, weapon types, movement modes.

```gdscript
class_name MovementStrategy
func move(body: CharacterBody2D, delta: float) -> void: pass

class WalkStrategy extends MovementStrategy:
    func move(body: CharacterBody2D, delta: float) -> void:
        var dir = Input.get_axis("left", "right")
        body.velocity.x = dir * 200.0
        body.move_and_slide()

class FlyStrategy extends MovementStrategy:
    func move(body: CharacterBody2D, delta: float) -> void:
        var dir = Vector2(
            Input.get_axis("left", "right"),
            Input.get_axis("up", "down")
        )
        body.velocity = dir * 300.0
        body.move_and_slide()

# Swap at runtime:
var strategy: MovementStrategy = WalkStrategy.new()
func enable_flight() -> void:
    strategy = FlyStrategy.new()
func _physics_process(delta: float) -> void:
    strategy.move(self, delta)
```

## Singleton (Autoload) — Use Sparingly

Good for: global game state, event bus, settings, save data.
Bad for: anything that should be instanced multiple times.

```gdscript
# GameState.gd (Autoload)
extends Node
var score: int = 0
var level: int = 1
var player_name: String = "Hero"
```

## Data-Driven Design

Store game data in resources or JSON, not in code.
Enables: designers to tweak without code, easy modding, clean separation.

```gdscript
# enemy_data.json
{
    "goblin": {"hp": 30, "speed": 80, "damage": 5, "xp": 10},
    "troll":  {"hp": 200, "speed": 40, "damage": 25, "xp": 50}
}

# Load once, use everywhere
var enemy_db: Dictionary = {}
func _ready() -> void:
    var file = FileAccess.open("res://data/enemy_data.json", FileAccess.READ)
    enemy_db = JSON.parse_string(file.get_as_text())

func spawn_enemy(type: String) -> void:
    var data = enemy_db[type]
    enemy.hp = data["hp"]
    enemy.speed = data["speed"]
```
""")


def write_reference_ai_local(dest: Path) -> None:
    _write_file(dest / "local_ai_model_guide.md", '''
# Local AI Model Guide: What to Run and Why

## Model Selection Framework

Ask three questions:
1. What task? (code, creative, chat, embeddings)
2. How much RAM? (GPU VRAM or CPU RAM)
3. Online or offline? (download now vs. later)

## The Quantization Trade-off

Quantization compresses model weights:
- Full (F16): highest quality, 2x model size in RAM
- Q8_0: ~5% quality loss, half the size of F16
- Q4_K_M: ~8-10% quality loss, ~1/4 the size — **sweet spot for USB**
- Q2_K: ~20% quality loss, very small — emergency use

**Rule of thumb**: Use Q4_K_M for everything on a 30GB USB.

## Models Worth Having (all fit in <6GB)

### General Intelligence
**dolphin3:8b-llama3.1-q4_K_M** (4.9 GB)
- Based on Llama 3.1 8B, fine-tuned for instruction following
- Uncensored (no system-prompt refusals)
- Best for: general chat, creative writing, reasoning, research
- Pull: `ollama pull dolphin3:8b-llama3.1-q4_K_M`

### Code Generation
**qwen2.5-coder:7b-instruct-q4_K_M** (4.7 GB)
- Alibaba's Qwen 2.5 Coder, specialized for code
- Excellent at GDScript, Python, JavaScript
- Supports function calling and structured output
- Pull: `ollama pull qwen2.5-coder:7b-instruct-q4_K_M`

### Embeddings (RAG)
**nomic-embed-text** (274 MB)
- Purpose-built embedding model
- 768-dimension vectors, strong recall
- Required by the WORDLIB RAG system
- Pull: `ollama pull nomic-embed-text`

## System Prompts Matter

The same model with different system prompts is almost a different model.

```python
# General assistant
system = "You are a helpful, direct assistant. Be concise and accurate."

# Code reviewer
system = """You are an expert code reviewer. When reviewing code:
- Point out bugs and security issues first
- Suggest specific improvements with examples
- Explain the WHY behind each suggestion
- Be direct, not diplomatic"""

# Game design advisor
system = """You are an experienced game designer specializing in indie games.
You balance creativity with practical constraints of small teams and limited budgets.
Always consider: player experience, development effort, and scope."""
```

## Temperature Guide

- **0.0-0.2**: Deterministic, factual, code (use for code generation)
- **0.3-0.5**: Balanced, slightly creative (use for most tasks)
- **0.6-0.8**: More creative, less predictable (use for brainstorming)
- **0.9-1.0**: Highly creative, sometimes incoherent (use sparingly)

## Context Window Limits

| Model | Context | Practical limit |
|-------|---------|-----------------|
| dolphin3 8B | 131K | ~40K (RAM limits) |
| qwen2.5-coder 7B | 32K | ~16K |

On USB: lower context = faster response. Use 4096 as default.

## RAG vs. Long Context

**Use RAG when**: documents are large, you have many docs, offline use
**Use long context when**: single document analysis, code review of full files

RAG with nomic-embed-text + dolphin3 = best offline knowledge retrieval.
Long context with dolphin3 = best for single-document deep analysis.

## Prompt Engineering Quick Reference

```python
# Chain of thought (better reasoning)
prompt = "Think through this step by step: " + question

# Few-shot (show examples)
prompt = f"""
Example: [input] -> [output]
Example: [input] -> [output]
Now do: {user_input}"""

# Structured output (JSON)
prompt = f"""Answer in JSON: {{"answer": ..., "confidence": 0-1, "reasoning": ...}}
Question: {question}"""

# Role + task + format
prompt = f"""
Role: Expert Python developer
Task: {task}
Format: Code block with comments, then brief explanation
"""
```
''')


# ═══════════════════════════════════════════════════════════════════════════
#  SEEDER ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class ContentSeeder:
    """Orchestrates all content seeding operations."""

    def __init__(self) -> None:
        self.gutenberg = GutenbergSource(cache_dir=CACHE)
        # Ensure all target dirs exist
        for d in (GUTENBERG_DIR, GODOT_DIR, GAMEDESIGN_DIR, REFERENCE_DIR):
            d.mkdir(parents=True, exist_ok=True)

    def seed_gutenberg(self, books: List[Tuple] = None) -> Dict[str, bool]:
        """Seed Project Gutenberg books."""
        books = books or GUTENBERG_BOOKS
        info(f"Seeding {len(books)} Gutenberg books into storage/gutenberg/")
        return self.gutenberg.seed_all(books, GUTENBERG_DIR)

    def seed_builtin(self) -> None:
        """Write all built-in knowledge files."""
        info("Writing Godot 4 knowledge files...")
        write_godot_architecture(GODOT_DIR)
        write_godot_optimization(GODOT_DIR)

        info("Writing game design knowledge files...")
        write_game_design_fundamentals(GAMEDESIGN_DIR)
        write_game_design_patterns(GAMEDESIGN_DIR)

        info("Writing AI reference files...")
        write_reference_ai_local(REFERENCE_DIR)

    def seed_all(self) -> None:
        """Seed everything."""
        print(f"\n{'='*56}")
        print(f"  WORDLIB Content Seeder -- Full Seed")
        print(f"{'='*56}\n")
        self.seed_builtin()
        print()
        self.seed_gutenberg()
        print()
        self._print_status()

    def seed_single_book(self, book_id: int) -> bool:
        """Seed a single Gutenberg book by ID."""
        # Check catalogue first
        match = [b for b in GUTENBERG_BOOKS if b[0] == book_id]
        if match:
            gid, slug, desc, chunk = match[0]
        else:
            # Unknown ID -- use defaults
            gid, slug, desc, chunk = book_id, f"book_{book_id}", f"Book {book_id}", 8000
        return self.gutenberg.seed_book(gid, slug, desc, chunk,
                                        GUTENBERG_DIR / slug)

    def _print_status(self) -> None:
        """Print status of all seeded content."""
        print(f"\n{'='*56}")
        print(f"  Storage Status")
        print(f"{'='*56}")
        total_files = 0
        total_bytes = 0
        for folder in sorted(STORAGE.iterdir()):
            if not folder.is_dir():
                continue
            files = list(folder.rglob("*.md")) + list(folder.rglob("*.txt"))
            size  = sum(f.stat().st_size for f in files)
            total_files += len(files)
            total_bytes += size
            print(f"  {folder.name:20s} {len(files):4d} files  "
                  f"{size/1024:.0f} KB")
        print(f"  {'─'*42}")
        print(f"  {'TOTAL':20s} {total_files:4d} files  "
              f"{total_bytes/1024:.0f} KB  "
              f"({total_bytes/1024/1024:.1f} MB)")
        print()


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="WORDLIB Content Seeder -- populate storage/ with real content",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python content_seeder.py --seed-all        # Seed everything (recommended)
  python content_seeder.py --builtin         # Built-in knowledge only (no internet)
  python content_seeder.py --gutenberg       # All Gutenberg books
  python content_seeder.py --book 1342       # Single book by Gutenberg ID
  python content_seeder.py --status          # Show what's already seeded
        """
    )
    parser.add_argument("--seed-all",  action="store_true", help="Seed all content")
    parser.add_argument("--gutenberg", action="store_true", help="Seed Gutenberg books only")
    parser.add_argument("--builtin",   action="store_true", help="Seed built-in knowledge only")
    parser.add_argument("--book",      type=int, metavar="ID", help="Seed a single Gutenberg book")
    parser.add_argument("--status",    action="store_true", help="Show seeding status")

    args = parser.parse_args()

    seeder = ContentSeeder()

    if args.seed_all:
        seeder.seed_all()
    elif args.gutenberg:
        results = seeder.seed_gutenberg()
        ok_count  = sum(1 for v in results.values() if v)
        fail_count = len(results) - ok_count
        print(f"\nDone: {ok_count} succeeded, {fail_count} failed")
    elif args.builtin:
        seeder.seed_builtin()
        ok("Built-in knowledge seeded.")
    elif args.book is not None:
        success = seeder.seed_single_book(args.book)
        (ok if success else err)(f"Book {args.book}: {'done' if success else 'FAILED'}")
    elif args.status:
        seeder._print_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


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

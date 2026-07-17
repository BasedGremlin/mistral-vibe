
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

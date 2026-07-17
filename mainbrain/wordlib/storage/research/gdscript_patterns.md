# GDScript 4.7 Patterns: Complete Reference

## Fundamentals

### Type System
```gdscript
var x: int = 5
var name: String = "player"
var items: Array[String] = ["sword", "shield"]
var data: Dictionary = {"hp": 100, "mp": 50}
var maybe: Variant = null  # Untyped, use sparingly

# Constants
const MAX_HEALTH: int = 100
const GRAVITY: float = 980.0
```

### Functions
```gdscript
func greet(player_name: String) -> String:
    return "Hello, %s!" % player_name

# Lambdas
var multiply = func(a: float, b: float) -> float: return a * b
print(multiply.call(3.0, 4.0))  # 12.0

# Static functions (no self access)
static func clamp_hp(value: int) -> int:
    return clamp(value, 0, MAX_HEALTH)
```

### Signals (event system)
```gdscript
# Define
signal health_changed(old_hp: int, new_hp: int)
signal player_died

# Emit
health_changed.emit(100, 75)
player_died.emit()

# Connect (in code)
health_changed.connect(_on_health_changed)
# Or one-shot:
player_died.connect(show_game_over, CONNECT_ONE_SHOT)

func _on_health_changed(old: int, new: int) -> void:
    print("HP: %d -> %d" % [old, new])
```

---

## Node Patterns

### Getting Nodes
```gdscript
# By path (fragile -- breaks if scene changes)
$Player/Sprite2D
get_node("Player/Sprite2D")

# By group (robust)
get_tree().get_nodes_in_group("enemies")

# By type (Godot 4.7)
var enemies = get_tree().get_nodes_in_group("enemies")
for enemy in enemies:
    if enemy is EnemyBase:
        enemy.take_damage(10)

# Unique name (editor sets %)
%PlayerHP  # %UniqueName syntax
```

### Autoloads (Singletons)
```gdscript
# In Project Settings > Autoload, add GameManager.gd as "GameManager"
# Access anywhere:
GameManager.current_level = 2
GameManager.player_score += 100
```

### Scene Instantiation
```gdscript
const BulletScene = preload("res://scenes/Bullet.tscn")

func shoot() -> void:
    var bullet = BulletScene.instantiate()
    bullet.position = muzzle.global_position
    bullet.direction = aim_direction
    get_tree().current_scene.add_child(bullet)
```

---

## Common Game Patterns

### State Machine
```gdscript
enum State { IDLE, WALK, RUN, ATTACK, DEAD }
var current_state: State = State.IDLE

func _physics_process(delta: float) -> void:
    match current_state:
        State.IDLE:   _process_idle(delta)
        State.WALK:   _process_walk(delta)
        State.ATTACK: _process_attack(delta)
        State.DEAD:   pass  # Do nothing

func _process_idle(delta: float) -> void:
    if Input.is_action_pressed("move_right"):
        current_state = State.WALK
```

### Character Movement (Top-Down)
```gdscript
extends CharacterBody2D

const SPEED: float = 200.0

func _physics_process(delta: float) -> void:
    var direction = Vector2(
        Input.get_axis("move_left", "move_right"),
        Input.get_axis("move_up", "move_down")
    ).normalized()
    
    velocity = direction * SPEED
    move_and_slide()
```

### Platformer Movement
```gdscript
extends CharacterBody2D

const SPEED: float = 300.0
const JUMP_VELOCITY: float = -600.0
const GRAVITY: float = 1200.0

func _physics_process(delta: float) -> void:
    if not is_on_floor():
        velocity.y += GRAVITY * delta
    
    if Input.is_action_just_pressed("jump") and is_on_floor():
        velocity.y = JUMP_VELOCITY
    
    velocity.x = Input.get_axis("move_left", "move_right") * SPEED
    move_and_slide()
```

### Save/Load System
```gdscript
const SAVE_PATH = "user://save.json"

func save_game(data: Dictionary) -> void:
    var file = FileAccess.open(SAVE_PATH, FileAccess.WRITE)
    file.store_string(JSON.stringify(data))

func load_game() -> Dictionary:
    if not FileAccess.file_exists(SAVE_PATH):
        return {}
    var file = FileAccess.open(SAVE_PATH, FileAccess.READ)
    return JSON.parse_string(file.get_as_text())
```

---

## Dialogic 2 Patterns

### Start a Timeline
```gdscript
Dialogic.start("res://dialogic/timelines/intro.dtl")
```

### Variables
```gdscript
# Set
Dialogic.VAR.player_name = "Johannes"
Dialogic.VAR.gold = 100

# Get
var name = Dialogic.VAR.player_name
```

### Signals
```gdscript
Dialogic.timeline_ended.connect(_on_dialog_end)
Dialogic.signal_event.connect(_on_dialogic_signal)

func _on_dialogic_signal(argument: String) -> void:
    match argument:
        "open_shop": open_shop()
        "start_battle": start_battle()
```

### Custom Portrait Animation
```gdscript
# In a portrait script
func _animate_portrait(portrait: Node, action: String) -> void:
    match action:
        "talking":
            portrait.play("talk")
        "idle":
            portrait.play("idle")
```

---

## Phantom Camera Patterns

### Basic Follow
```gdscript
# Add PhantomCamera2D to scene
# Set Follow Target to your player node
# Adjust Dead Zone for follow tolerance
```

### Code Control
```gdscript
var pcam: PhantomCamera2D

func _ready() -> void:
    pcam = $PhantomCamera2D

func zoom_in() -> void:
    pcam.zoom = Vector2(2.0, 2.0)

func set_target(new_target: Node2D) -> void:
    pcam.follow_target = new_target

# Prioritize a camera (useful for cutscenes)
func start_cutscene() -> void:
    $CutsceneCamera.priority = 10  # Higher priority = active
```

---

## Performance Tips

### Object Pooling
```gdscript
class_name BulletPool extends Node

var pool: Array[Bullet] = []
const POOL_SIZE: int = 50

func _ready() -> void:
    for i in POOL_SIZE:
        var b = BulletScene.instantiate()
        b.visible = false
        add_child(b)
        pool.append(b)

func get_bullet() -> Bullet:
    for b in pool:
        if not b.visible:
            b.visible = true
            return b
    return null  # Pool exhausted

func return_bullet(b: Bullet) -> void:
    b.visible = false
    b.position = Vector2.ZERO
```

### Deferred Calls (avoid frame-order issues)
```gdscript
# Instead of:
queue_free()
# Use inside signal handlers:
queue_free.call_deferred()

# Or schedule expensive work:
call_deferred("_heavy_computation")
```

### Groups for Batch Operations
```gdscript
# Tag enemies at spawn:
add_to_group("enemies")

# Kill all enemies:
get_tree().call_group("enemies", "die")

# Get count:
get_tree().get_nodes_in_group("enemies").size()
```

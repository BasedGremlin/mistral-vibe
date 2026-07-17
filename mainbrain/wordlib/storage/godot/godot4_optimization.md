
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

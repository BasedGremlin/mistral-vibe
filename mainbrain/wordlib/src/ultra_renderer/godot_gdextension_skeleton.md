# Priority 8: Godot GDExtension Skeleton

This document outlines how the UltraRenderer could be exposed to Godot as a GDExtension.

## High-Level Architecture

```
Godot (GDScript / C#)
        ↓
GDExtension (C++ / Rust)
        ↓
UltraRenderer Core (C++ or ported from Python/Numba logic)
        ↓
Vulkan Backend (from Priority 7)
```

## Recommended Technology Stack

- **Language**: C++ (official) or Rust (using `gdext` crate)
- **Build System**: CMake + `godot-cpp` (for C++)
- **Rendering**: Vulkan (from the skeleton in `vulkan_skeleton.py`)

## Proposed Class Structure (C++)

```cpp
// ultra_renderer.h
#include <godot_cpp/classes/ref_counted.hpp>
#include <godot_cpp/variant/vector3.hpp>

class UltraRenderer : public godot::RefCounted {
    GDCLASS(UltraRenderer, godot::RefCounted);

public:
    void set_resolution(int width, int height);
    void set_quality_level(const godot::String& level); // "HIGH" or "ULTRA"

    void render_frame();                    // Main render call
    godot::Ref<godot::Image> get_output();  // Returns rendered image as Godot Image

    // Camera control
    void set_camera_transform(const godot::Transform3D& transform);

    // Light management
    void add_point_light(const godot::Vector3& position, const godot::Color& color, float intensity);

protected:
    static void _bind_methods();
};
```

## Integration Points with Godot

1. **RenderingServer** integration (for custom rendering)
2. Expose G-buffer textures as `ImageTexture` or `Texture2DRD`
3. Allow Godot nodes to register geometry (meshes + materials)
4. Expose `RenderGraph` quality settings to GDScript

## Benefits of GDExtension Approach

- High performance (native code + Vulkan)
- Full access to Godot's scene tree and nodes
- Can be distributed as a single `.gdextension` file + binaries
- Future-proof (Godot 4.x GDExtension is stable)

## Recommended Development Path

1. Finish Vulkan backend (Priority 7)
2. Create minimal C++ wrapper around the renderer
3. Expose basic API (`render()`, `set_camera()`, `add_light()`)
4. Integrate with Godot's `RenderingDevice` for zero-copy texture sharing
5. Add geometry submission from Godot meshes

This would turn UltraRenderer into a powerful custom renderer module for Godot.

#!/usr/bin/env python3
"""
Priority 6: Shadow Atlas

A simplified shadow atlas system for managing multiple light shadows
in a single large texture. Includes basic PCF (Percentage Closer Filtering)
for soft shadows.

This is designed to work with the existing RenderGraph and clustered lighting.
"""

import numpy as np
# Optional Numba for production parallel JIT (graceful fallback if absent)
try:
    from numba import njit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range  # fallback: serial range when no Numba
class ShadowAtlas:
    """
    Manages a large shadow map atlas for multiple lights.
    Each light gets a region in the atlas.
    """

    def __init__(self, atlas_size=1024, tile_size=128):
        self.atlas_size = atlas_size
        self.tile_size = tile_size
        self.tiles_per_row = atlas_size // tile_size
        self.shadow_atlas = np.full((atlas_size, atlas_size), 1e9, dtype=np.float32)
        self.light_to_tile = {}   # light_index -> (tile_x, tile_y)
        self.next_tile = 0

    def allocate_tile(self, light_index):
        """Allocate a tile in the atlas for a light."""
        if light_index in self.light_to_tile:
            return self.light_to_tile[light_index]

        if self.next_tile >= self.tiles_per_row * self.tiles_per_row:
            # Atlas full - in real engine we'd evict or resize
            return None

        tx = self.next_tile % self.tiles_per_row
        ty = self.next_tile // self.tiles_per_row

        self.light_to_tile[light_index] = (tx, ty)
        self.next_tile += 1
        return (tx, ty)

    def get_shadow_uv(self, light_index, world_pos):
        """Convert world position to UV in the shadow atlas for a specific light."""
        if light_index not in self.light_to_tile:
            return None

        tx, ty = self.light_to_tile[light_index]
        # This is a placeholder. In a real implementation we would
        # transform world_pos using the light's view-projection matrix.
        # For now we return a dummy UV inside the tile.
        u = (tx + 0.5) / self.tiles_per_row
        v = (ty + 0.5) / self.tiles_per_row
        return u, v

    def clear(self):
        self.shadow_atlas.fill(1e9)
        self.light_to_tile.clear()
        self.next_tile = 0


@njit(fastmath=True)
def sample_shadow_pcf(atlas, atlas_size, tile_size, u, v, compare_depth, samples=4):
    """
    Simple Percentage Closer Filtering (PCF) for soft shadows.
    Samples around the UV coordinate.
    """
    if u is None or v is None:
        return 1.0  # No shadow

    tx = int(u * (atlas_size / tile_size))
    ty = int(v * (atlas_size / tile_size))

    shadow = 0.0
    step = 1.0 / tile_size

    for dy in range(-1, 2):
        for dx in range(-1, 2):
            su = u + dx * step * 0.5
            sv = v + dy * step * 0.5

            sx = int(su * atlas_size)
            sy = int(sv * atlas_size)

            if 0 <= sx < atlas_size and 0 <= sy < atlas_size:
                shadow_depth = atlas[sy, sx]
                if compare_depth < shadow_depth + 0.01:
                    shadow += 1.0

    return shadow / 9.0   # 3x3 PCF


# Example integration stub
if __name__ == "__main__":
    print("Shadow Atlas Test")
    atlas = ShadowAtlas(atlas_size=512, tile_size=128)
    tile = atlas.allocate_tile(light_index=0)
    print("Allocated tile for light 0:", tile)

    uv = atlas.get_shadow_uv(0, np.array([0.0, 0.0, 10.0]))
    print("Shadow UV:", uv)
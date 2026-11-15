"""Create a smaller, visual-only Moon model from NASA's original GLB.

Requires numpy and Pillow. The source asset remains unchanged.
"""

import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image


ASSETS = Path(__file__).resolve().parents[1] / "assets"
SOURCE = ASSETS / "moon.glb"
OUTPUT = ASSETS / "moon-optimized.glb"


def main() -> None:
    raw = SOURCE.read_bytes()
    magic, version, _ = struct.unpack_from("<4sII", raw, 0)
    json_length = struct.unpack_from("<I", raw, 12)[0]
    document = json.loads(raw[20 : 20 + json_length])
    binary_chunk = 20 + json_length
    binary_length, _ = struct.unpack_from("<I4s", raw, binary_chunk)
    original_binary = raw[binary_chunk + 8 : binary_chunk + 8 + binary_length]
    views = document["bufferViews"]
    accessors = document["accessors"]

    def read_accessor(index: int, dtype: str, width: int) -> np.ndarray:
        accessor = accessors[index]
        view = views[accessor["bufferView"]]
        offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
        return np.frombuffer(
            original_binary,
            dtype=dtype,
            count=accessor["count"] * width,
            offset=offset,
        ).reshape(-1, width).copy()

    positions = read_accessor(0, "<f4", 3)
    normals = read_accessor(1, "<f4", 3)
    uvs = read_accessor(2, "<f4", 2)
    indices = read_accessor(3, "<u4", 1).ravel().reshape(-1, 3)

    # Cluster nearby vertices and keep UV splits so the original texture atlas
    # remains aligned. Shared positions prevent gaps at UV seams.
    position_keys = np.rint(positions / 0.02).astype(np.int32)
    uv_keys = np.rint(uvs / 0.04).astype(np.int32)
    keys = np.column_stack((position_keys, uv_keys))
    _, inverse = np.unique(keys, axis=0, return_inverse=True)
    key_count = int(inverse.max()) + 1

    _, position_inverse = np.unique(position_keys, axis=0, return_inverse=True)
    position_count = int(position_inverse.max()) + 1
    position_sums = np.zeros((position_count, 3), dtype=np.float64)
    np.add.at(position_sums, position_inverse, positions)
    position_weights = np.bincount(position_inverse, minlength=position_count)
    shared_positions = (position_sums / position_weights[:, None]).astype(np.float32)

    representatives = np.full(key_count, len(inverse), dtype=np.int64)
    np.minimum.at(representatives, inverse, np.arange(len(inverse)))
    clustered_positions = shared_positions[position_inverse[representatives]]

    uv_sums = np.zeros((key_count, 2), dtype=np.float64)
    normal_sums = np.zeros((key_count, 3), dtype=np.float64)
    weights = np.bincount(inverse, minlength=key_count)
    np.add.at(uv_sums, inverse, uvs)
    np.add.at(normal_sums, inverse, normals)
    clustered_uvs = (uv_sums / weights[:, None]).astype(np.float32)
    clustered_normals = normal_sums / weights[:, None]
    clustered_normals /= np.maximum(
        np.linalg.norm(clustered_normals, axis=1)[:, None], 1e-12
    )
    clustered_normals = clustered_normals.astype(np.float32)

    triangles = inverse[indices]
    valid = (
        (triangles[:, 0] != triangles[:, 1])
        & (triangles[:, 1] != triangles[:, 2])
        & (triangles[:, 2] != triangles[:, 0])
    )
    triangles = triangles[valid]
    used, compact = np.unique(triangles, return_inverse=True)
    triangles = compact.reshape(-1, 3).astype("<u4")
    positions_out = clustered_positions[used]
    normals_out = clustered_normals[used]
    uvs_out = clustered_uvs[used]

    output_binary = bytearray()
    output_views: list[dict[str, int]] = []

    def add_view(array: np.ndarray, target: int) -> int:
        while len(output_binary) % 4:
            output_binary.append(0)
        offset = len(output_binary)
        payload = array.tobytes(order="C")
        output_binary.extend(payload)
        output_views.append(
            {"buffer": 0, "byteOffset": offset, "byteLength": len(payload), "target": target}
        )
        return len(output_views) - 1

    accessors[0].update(
        bufferView=add_view(positions_out, 34962),
        byteOffset=0,
        count=len(positions_out),
        min=positions_out.min(axis=0).tolist(),
        max=positions_out.max(axis=0).tolist(),
    )
    accessors[1].update(bufferView=add_view(normals_out, 34962), byteOffset=0, count=len(normals_out))
    accessors[2].update(bufferView=add_view(uvs_out, 34962), byteOffset=0, count=len(uvs_out))
    flat_indices = triangles.ravel()
    accessors[3].update(
        bufferView=add_view(flat_indices, 34963),
        byteOffset=0,
        count=len(flat_indices),
        min=[int(flat_indices.min())],
        max=[int(flat_indices.max())],
    )

    image = document["images"][0]
    old_view = views[image["bufferView"]]
    image_offset = old_view.get("byteOffset", 0)
    texture = Image.open(
        io.BytesIO(original_binary[image_offset : image_offset + old_view["byteLength"]])
    ).convert("RGB")
    texture.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    encoded_texture = io.BytesIO()
    texture.save(encoded_texture, "JPEG", quality=86, optimize=True)
    while len(output_binary) % 4:
        output_binary.append(0)
    texture_offset = len(output_binary)
    texture_bytes = encoded_texture.getvalue()
    output_binary.extend(texture_bytes)
    output_views.append(
        {"buffer": 0, "byteOffset": texture_offset, "byteLength": len(texture_bytes)}
    )
    image["bufferView"] = len(output_views) - 1
    image["mimeType"] = "image/jpeg"

    document["bufferViews"] = output_views
    document["buffers"][0]["byteLength"] = len(output_binary)
    json_chunk = json.dumps(document, separators=(",", ":")).encode()
    json_chunk += b" " * (-len(json_chunk) % 4)
    output_binary += b"\0" * (-len(output_binary) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(output_binary)
    result = (
        struct.pack("<4sII", magic, version, total_length)
        + struct.pack("<I4s", len(json_chunk), b"JSON")
        + json_chunk
        + struct.pack("<I4s", len(output_binary), b"BIN\0")
        + output_binary
    )
    OUTPUT.write_bytes(result)
    print(
        f"Wrote {OUTPUT.name}: {len(positions):,} -> {len(positions_out):,} vertices, "
        f"{len(indices):,} -> {len(triangles):,} triangles, "
        f"{len(raw):,} -> {len(result):,} bytes"
    )


if __name__ == "__main__":
    main()

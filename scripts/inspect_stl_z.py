#!/usr/bin/env python3
"""Report basic Z-level structure for binary STL files."""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path


Triangle = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def read_triangles(path: Path) -> list[Triangle]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"{path} is too small to be a binary STL")
    count = struct.unpack("<I", data[80:84])[0]
    expected_len = 84 + count * 50
    if expected_len != len(data):
        raise ValueError(f"{path} does not look like a binary STL")

    triangles: list[Triangle] = []
    offset = 84
    for _ in range(count):
        offset += 12
        tri = []
        for _ in range(3):
            tri.append(struct.unpack("<fff", data[offset : offset + 12]))
            offset += 12
        offset += 2
        triangles.append((tri[0], tri[1], tri[2]))
    return triangles


def read_z_values(path: Path) -> tuple[int, list[float]]:
    triangles = read_triangles(path)
    return len(triangles), [point[2] for tri in triangles for point in tri]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stls", nargs="+", type=Path)
    parser.add_argument("--edge-count", type=int, default=24)
    parser.add_argument("--plane", action="append", type=float, default=[])
    parser.add_argument("--tolerance", type=float, default=0.001)
    args = parser.parse_args()

    for path in args.stls:
        triangles = read_triangles(path)
        count = len(triangles)
        zs = [point[2] for tri in triangles for point in tri]
        levels = sorted({round(z, 4) for z in zs})
        print(path)
        print(f"  triangles: {count}")
        print(f"  z range: {min(zs):.4f} .. {max(zs):.4f}")
        print(f"  unique rounded z levels: {len(levels)}")
        print(f"  first levels: {levels[:args.edge_count]}")
        print(f"  last levels: {levels[-args.edge_count:]}")
        for plane in args.plane:
            matching = [
                tri
                for tri in triangles
                if all(math.isclose(point[2], plane, abs_tol=args.tolerance) for point in tri)
            ]
            if not matching:
                print(f"  plane {plane:.4f}: no coplanar triangles")
                continue
            xs = [point[0] for tri in matching for point in tri]
            ys = [point[1] for tri in matching for point in tri]
            print(
                f"  plane {plane:.4f}: {len(matching)} triangles, "
                f"xy bounds {min(xs):.4f},{min(ys):.4f} .. {max(xs):.4f},{max(ys):.4f}"
            )


if __name__ == "__main__":
    main()

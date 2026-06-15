#!/usr/bin/env python3
"""Create a tiny binary STL frame for testing the stack/interstitial workflow."""

from __future__ import annotations

import math
import struct
from pathlib import Path


Point = tuple[float, float, float]
Triangle = tuple[Point, Point, Point]


def normal_for(triangle: Triangle) -> Point:
    a, b, c = triangle
    ux, uy, uz = (b[i] - a[i] for i in range(3))
    vx, vy, vz = (c[i] - a[i] for i in range(3))
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (nx / length, ny / length, nz / length)


def quad(a: Point, b: Point, c: Point, d: Point) -> list[Triangle]:
    return [(a, b, c), (a, c, d)]


def box(x0: float, y0: float, x1: float, y1: float, z0: float, z1: float) -> list[Triangle]:
    p000 = (x0, y0, z0)
    p100 = (x1, y0, z0)
    p110 = (x1, y1, z0)
    p010 = (x0, y1, z0)
    p001 = (x0, y0, z1)
    p101 = (x1, y0, z1)
    p111 = (x1, y1, z1)
    p011 = (x0, y1, z1)
    triangles: list[Triangle] = []
    triangles.extend(quad(p000, p010, p110, p100))
    triangles.extend(quad(p001, p101, p111, p011))
    triangles.extend(quad(p000, p100, p101, p001))
    triangles.extend(quad(p100, p110, p111, p101))
    triangles.extend(quad(p110, p010, p011, p111))
    triangles.extend(quad(p010, p000, p001, p011))
    return triangles


def write_binary_stl(path: Path, triangles: list[Triangle]) -> None:
    header = b"demo frame".ljust(80, b" ")
    with path.open("wb") as fh:
        fh.write(header)
        fh.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            fh.write(struct.pack("<fff", *normal_for(triangle)))
            for vertex in triangle:
                fh.write(struct.pack("<fff", *vertex))
            fh.write(struct.pack("<H", 0))


def main() -> None:
    path = Path(__file__).with_name("demo-frame.stl")
    triangles: list[Triangle] = []
    height = 4.0
    outer = 40.0
    rail = 6.0
    triangles.extend(box(0, 0, outer, rail, 0, height))
    triangles.extend(box(0, outer - rail, outer, outer, 0, height))
    triangles.extend(box(0, rail, rail, outer - rail, 0, height))
    triangles.extend(box(outer - rail, rail, outer, outer - rail, 0, height))
    write_binary_stl(path, triangles)
    print(path)
    print(f"triangles: {len(triangles)}")


if __name__ == "__main__":
    main()

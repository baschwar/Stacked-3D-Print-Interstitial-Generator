"""Shared helpers for reading and inspecting binary STL geometry."""

from __future__ import annotations

import math
import struct
from pathlib import Path


Point = tuple[float, float, float]
Triangle = tuple[Point, Point, Point]


def read_binary_stl(path: Path) -> list[Triangle]:
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
        vertices = []
        for _ in range(3):
            vertices.append(struct.unpack("<fff", data[offset : offset + 12]))
            offset += 12
        offset += 2
        triangles.append((vertices[0], vertices[1], vertices[2]))
    return triangles


def bounds(triangles: list[Triangle]) -> tuple[Point, Point]:
    if not triangles:
        raise ValueError("Cannot calculate bounds for an empty triangle list")
    points = [point for tri in triangles for point in tri]
    mins = tuple(min(point[i] for point in points) for i in range(3))
    maxs = tuple(max(point[i] for point in points) for i in range(3))
    return mins, maxs


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


def triangle_area_xy(triangle: Triangle) -> float:
    (ax, ay, _az), (bx, by, _bz), (cx, cy, _cz) = triangle
    return abs((ax * (by - cy) + bx * (cy - ay) + cx * (ay - by)) / 2)


def plane_faces(triangles: list[Triangle], plane_z: float, tolerance: float) -> list[Triangle]:
    return [
        tri
        for tri in triangles
        if all(math.isclose(point[2], plane_z, abs_tol=tolerance) for point in tri)
    ]


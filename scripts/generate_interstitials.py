#!/usr/bin/env python3
"""Create aligned interstitial separator STLs for already-stacked binary STL files."""

from __future__ import annotations

import argparse
import math
import struct
from collections import Counter
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


def write_binary_stl(path: Path, triangles: list[Triangle], title: str) -> None:
    header = title.encode("ascii", errors="replace")[:80].ljust(80, b" ")
    with path.open("wb") as fh:
        fh.write(header)
        fh.write(struct.pack("<I", len(triangles)))
        for tri in triangles:
            fh.write(struct.pack("<fff", *normal_for(tri)))
            for vertex in tri:
                fh.write(struct.pack("<fff", *vertex))
            fh.write(struct.pack("<H", 0))


def quantize_xy(point: Point, precision: int) -> tuple[float, float]:
    return (round(point[0], precision), round(point[1], precision))


def plane_faces(triangles: list[Triangle], plane_z: float, tolerance: float) -> list[Triangle]:
    return [
        tri
        for tri in triangles
        if all(math.isclose(point[2], plane_z, abs_tol=tolerance) for point in tri)
    ]


def quad_triangles(a: Point, b: Point, c: Point, d: Point) -> list[Triangle]:
    return [(a, b, c), (a, c, d)]


def box_from_edge(a: Point, b: Point, bottom_z: float, thickness: float, outset: float) -> list[Triangle]:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return []
    nx = -dy / length
    ny = dx / length

    p0 = (a[0], a[1], bottom_z)
    p1 = (b[0], b[1], bottom_z)
    p2 = (b[0] + nx * outset, b[1] + ny * outset, bottom_z)
    p3 = (a[0] + nx * outset, a[1] + ny * outset, bottom_z)
    q0 = (p0[0], p0[1], bottom_z + thickness)
    q1 = (p1[0], p1[1], bottom_z + thickness)
    q2 = (p2[0], p2[1], bottom_z + thickness)
    q3 = (p3[0], p3[1], bottom_z + thickness)

    triangles: list[Triangle] = []
    triangles.extend(quad_triangles(p0, p3, p2, p1))
    triangles.extend(quad_triangles(q0, q1, q2, q3))
    triangles.extend(quad_triangles(p0, p1, q1, q0))
    triangles.extend(quad_triangles(p1, p2, q2, q1))
    triangles.extend(quad_triangles(p2, p3, q3, q2))
    triangles.extend(quad_triangles(p3, p0, q0, q3))
    return triangles


def extrude_faces(
    faces: list[Triangle],
    bottom_z: float,
    thickness: float,
    precision: int,
    edge_outset: float,
) -> list[Triangle]:
    top_z = bottom_z + thickness
    output: list[Triangle] = []

    for tri in faces:
        bottom = tuple((x, y, bottom_z) for x, y, _z in tri)
        top = tuple((x, y, top_z) for x, y, _z in tri)
        output.append((bottom[2], bottom[1], bottom[0]))
        output.append((top[0], top[1], top[2]))

    edge_counter: Counter[tuple[tuple[float, float], tuple[float, float]]] = Counter()
    edge_points: dict[tuple[tuple[float, float], tuple[float, float]], tuple[Point, Point]] = {}
    edge_centroids: dict[tuple[tuple[float, float], tuple[float, float]], Point] = {}
    for tri in faces:
        centroid = (
            sum(point[0] for point in tri) / 3,
            sum(point[1] for point in tri) / 3,
            sum(point[2] for point in tri) / 3,
        )
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            qa = quantize_xy(a, precision)
            qb = quantize_xy(b, precision)
            key = tuple(sorted((qa, qb)))
            edge_counter[key] += 1
            edge_points[key] = (a, b)
            edge_centroids[key] = centroid

    for key, count in edge_counter.items():
        if count != 1:
            continue
        a, b = edge_points[key]
        ab = (a[0], a[1], bottom_z)
        bb = (b[0], b[1], bottom_z)
        at = (a[0], a[1], top_z)
        bt = (b[0], b[1], top_z)
        output.append((ab, bb, bt))
        output.append((ab, bt, at))
        if edge_outset > 0:
            centroid = edge_centroids[key]
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            length = math.hypot(dx, dy)
            if length > 0:
                left = (-dy / length, dx / length)
                midpoint = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                to_centroid = (centroid[0] - midpoint[0], centroid[1] - midpoint[1])
                if left[0] * to_centroid[0] + left[1] * to_centroid[1] > 0:
                    a, b = b, a
                output.extend(box_from_edge(a, b, bottom_z, thickness, edge_outset))

    return output


def default_planes(start: float, step: float, stack_count: int) -> list[float]:
    return [start + index * step for index in range(stack_count - 1)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Extract horizontal interface faces from an already-stacked STL and "
            "extrude them into a standalone, aligned separator STL for support "
            "or release material."
        )
    )
    parser.add_argument("stls", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("interstitial-output"))
    parser.add_argument("--stack-count", type=int, default=8)
    parser.add_argument("--first-interface-z", type=float, default=0.2)
    parser.add_argument("--interface-step", type=float, default=4.4)
    parser.add_argument("--thickness", type=float, default=0.2)
    parser.add_argument(
        "--edge-outset",
        type=float,
        default=0.0,
        help="Add this many mm of extra separator around each boundary edge.",
    )
    parser.add_argument("--tolerance", type=float, default=0.001)
    parser.add_argument("--precision", type=int, default=4)
    args = parser.parse_args()

    if args.stack_count < 2:
        raise ValueError("--stack-count must be at least 2")
    if args.thickness <= 0:
        raise ValueError("--thickness must be positive")
    if args.edge_outset < 0:
        raise ValueError("--edge-outset must be zero or greater")

    planes = default_planes(args.first_interface_z, args.interface_step, args.stack_count)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for stl in args.stls:
        source = read_binary_stl(stl)
        separator_triangles: list[Triangle] = []
        print(stl)
        for index, plane_z in enumerate(planes, start=1):
            faces = plane_faces(source, plane_z, args.tolerance)
            if not faces:
                raise ValueError(f"{stl}: no horizontal faces found at z={plane_z:.4f}")
            layer = extrude_faces(faces, plane_z, args.thickness, args.precision, args.edge_outset)
            separator_triangles.extend(layer)
            kind = "first-normal-to-flipped" if index == 1 else "flipped-to-flipped"
            print(
                f"  separator {index}: z {plane_z:.4f}..{plane_z + args.thickness:.4f}, "
                f"{kind}, source faces {len(faces)}, output triangles {len(layer)}"
            )

        outset_slug = f" {args.edge_outset:.2f}mm outset" if args.edge_outset else ""
        output = args.output_dir / f"{stl.stem} - interstitials {args.thickness:.2f}mm{outset_slug}.stl"
        write_binary_stl(output, separator_triangles, f"{stl.stem} interstitials")
        print(f"  wrote {output}")
        print(f"  total separator triangles: {len(separator_triangles)}")


if __name__ == "__main__":
    main()

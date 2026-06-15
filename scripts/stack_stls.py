#!/usr/bin/env python3
"""Create vertical test stacks from existing binary STL files."""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path


Triangle = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Orientation = str


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


def bounds(triangles: list[Triangle]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    points = [point for tri in triangles for point in tri]
    mins = tuple(min(point[i] for point in points) for i in range(3))
    maxs = tuple(max(point[i] for point in points) for i in range(3))
    return mins, maxs


def normal_for(triangle: Triangle) -> tuple[float, float, float]:
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


def parse_orientation_pattern(pattern: str | None) -> list[Orientation]:
    if not pattern:
        return ["normal"]

    aliases = {
        "n": "normal",
        "normal": "normal",
        "up": "normal",
        "f": "flip",
        "flip": "flip",
        "flipped": "flip",
        "down": "flip",
        "180": "flip",
    }
    orientations = []
    for raw_item in pattern.split(","):
        item = raw_item.strip().lower()
        if not item:
            continue
        if item not in aliases:
            valid = ", ".join(sorted(set(aliases)))
            raise ValueError(f"Unknown orientation '{raw_item}'. Use one of: {valid}")
        orientations.append(aliases[item])

    if not orientations:
        raise ValueError("--orientation-pattern must include at least one orientation")
    return orientations


def transform_stack(
    triangles: list[Triangle],
    copies: int,
    gap: float,
    orientation_pattern: list[Orientation],
) -> list[Triangle]:
    mins, maxs = bounds(triangles)
    z_height = maxs[2] - mins[2]
    center_y = (mins[1] + maxs[1]) / 2
    center_z = (mins[2] + maxs[2]) / 2
    stacked: list[Triangle] = []

    for copy_index in range(copies):
        orientation = orientation_pattern[copy_index % len(orientation_pattern)]
        flip = orientation == "flip"
        z_offset = copy_index * (z_height + gap) - mins[2]
        for tri in triangles:
            transformed = []
            for x, y, z in tri:
                if flip:
                    y = 2 * center_y - y
                    z = 2 * center_z - z
                transformed.append((x - mins[0], y - mins[1], z + z_offset))

            if flip:
                transformed = [transformed[0], transformed[2], transformed[1]]
            stacked.append((transformed[0], transformed[1], transformed[2]))

    return stacked


def pattern_for_output(orientation_pattern: list[Orientation], copies: int) -> str:
    expanded = [orientation_pattern[index % len(orientation_pattern)] for index in range(copies)]
    if all(item == "normal" for item in expanded):
        return "normal"
    if expanded == ["normal"] + ["flip"] * (copies - 1):
        return "normal-then-flipped"
    return "-".join("n" if item == "normal" else "f" for item in expanded)


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create repeated vertical STL stacks. By default every copy is normal. "
            "Use --orientation-pattern to control each layer's orientation."
        )
    )
    parser.add_argument("stls", nargs="+", type=Path)
    parser.add_argument("--copies", type=int, default=4, help="Number of copies in each stack.")
    parser.add_argument("--gap", type=float, default=0.20, help="Z gap in mm between copies.")
    parser.add_argument("--output-dir", type=Path, default=Path("stacked-output"))
    parser.add_argument(
        "--orientation-pattern",
        help=(
            "Comma-separated layer pattern. Values: normal/n/up or flip/f/down/180. "
            "The pattern repeats when it is shorter than --copies."
        ),
    )
    parser.add_argument(
        "--flipped-after-first",
        action="store_true",
        help="Shortcut for --orientation-pattern normal,flip,flip,...",
    )
    args = parser.parse_args()

    if args.copies < 1:
        raise ValueError("--copies must be at least 1")
    if args.gap < 0:
        raise ValueError("--gap must be zero or greater")

    orientation_pattern = parse_orientation_pattern(args.orientation_pattern)
    if args.flipped_after_first:
        if args.orientation_pattern:
            raise ValueError("Use either --orientation-pattern or --flipped-after-first, not both")
        orientation_pattern = ["normal"] + ["flip"] * max(0, args.copies - 1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for stl in args.stls:
        triangles = read_binary_stl(stl)
        stacked = transform_stack(
            triangles,
            copies=args.copies,
            gap=args.gap,
            orientation_pattern=orientation_pattern,
        )
        orientation_slug = pattern_for_output(orientation_pattern, args.copies)
        output = args.output_dir / (
            f"{stl.stem} - {args.copies}up stack {args.gap:.2f}mm gap {orientation_slug}.stl"
        )
        write_binary_stl(output, stacked, f"{stl.stem} {args.copies}up stack")
        mins, maxs = bounds(stacked)
        size = tuple(maxs[i] - mins[i] for i in range(3))
        print(f"{output}")
        print(f"  triangles: {len(stacked)}")
        print(f"  size mm: {size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f}")
        print(f"  orientation: {orientation_slug}")


if __name__ == "__main__":
    main()

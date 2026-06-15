#!/usr/bin/env python3
"""Report whether STL files are good candidates for vertical stack printing."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from collections import defaultdict
from pathlib import Path

try:
    from stl_utils import Point, Triangle, bounds, plane_faces, read_binary_stl, triangle_area_xy
except ModuleNotFoundError:
    from scripts.stl_utils import Point, Triangle, bounds, plane_faces, read_binary_stl, triangle_area_xy


@dataclass(frozen=True)
class StackabilityReport:
    footprint_area_mm2: float
    height_mm: float
    footprint_to_height_ratio: float
    stackability_score: int
    rating: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class BedAreaSavingsReport:
    copies: int
    stack_count: int
    copies_per_flat_bed: int
    stacks_needed: int
    stacks_per_bed: int
    flat_beds_needed: int
    stacked_beds_needed: int
    bed_batch_savings: int
    stacked_height_mm: float


@dataclass(frozen=True)
class InterfaceQualityReport:
    plane_z: float
    classification: str
    face_count: int
    projected_area_mm2: float
    footprint_coverage_ratio: float
    component_count: int
    largest_component_area_mm2: float


def clamp_score(score: float) -> int:
    return max(0, min(100, round(score)))


def parse_bed_size(raw: str) -> tuple[float, float]:
    normalized = raw.lower().replace(",", "x")
    parts = [part.strip() for part in normalized.split("x") if part.strip()]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--bed-size must look like WIDTHxDEPTH, for example 256x256")
    try:
        width, depth = (float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--bed-size values must be numbers") from exc
    if width <= 0 or depth <= 0:
        raise argparse.ArgumentTypeError("--bed-size values must be positive")
    return width, depth


def box_size(triangles: list[Triangle]) -> Point:
    mins, maxs = bounds(triangles)
    return tuple(maxs[i] - mins[i] for i in range(3))


def classify_stackability(triangles: list[Triangle]) -> StackabilityReport:
    mins, maxs = bounds(triangles)
    width = maxs[0] - mins[0]
    depth = maxs[1] - mins[1]
    height = maxs[2] - mins[2]
    footprint_area = width * depth
    ratio = footprint_area / height if height > 0 else 0.0

    top_z = maxs[2]
    bottom_z = mins[2]
    top_area = sum(triangle_area_xy(tri) for tri in triangles if all(point[2] == top_z for point in tri))
    bottom_area = sum(triangle_area_xy(tri) for tri in triangles if all(point[2] == bottom_z for point in tri))
    smaller_interface = min(top_area, bottom_area)
    interface_ratio = smaller_interface / footprint_area if footprint_area > 0 else 0.0

    score = 0.0
    reasons: list[str] = []

    if ratio >= 200:
        score += 45
        reasons.append("large XY footprint relative to height")
    elif ratio >= 75:
        score += 30
        reasons.append("moderate XY footprint relative to height")
    else:
        score += 10
        reasons.append("small XY footprint relative to height")

    if interface_ratio >= 0.60:
        score += 45
        reasons.append("broad flat top and bottom interface area")
    elif interface_ratio >= 0.20:
        score += 25
        reasons.append("some usable flat interface area")
    else:
        score += 5
        reasons.append("limited flat interface area")

    if height <= 15:
        score += 10
        reasons.append("low part height")
    elif height <= 50:
        score += 5
        reasons.append("moderate part height")
    else:
        reasons.append("tall part height")

    final_score = clamp_score(score)
    if final_score >= 80:
        rating = "strong"
    elif final_score >= 60:
        rating = "possible"
    else:
        rating = "weak"

    return StackabilityReport(
        footprint_area_mm2=footprint_area,
        height_mm=height,
        footprint_to_height_ratio=ratio,
        stackability_score=final_score,
        rating=rating,
        reasons=tuple(reasons),
    )


def copies_per_bed(width: float, depth: float, bed_width: float, bed_depth: float) -> int:
    if width <= 0 or depth <= 0:
        return 0
    normal = math.floor(bed_width / width) * math.floor(bed_depth / depth)
    rotated = math.floor(bed_width / depth) * math.floor(bed_depth / width)
    return max(normal, rotated)


def estimate_bed_area_savings(
    triangles: list[Triangle],
    copies: int,
    stack_count: int,
    gap: float,
    bed_size: tuple[float, float],
) -> BedAreaSavingsReport:
    if copies < 1:
        raise ValueError("copies must be at least 1")
    if stack_count < 1:
        raise ValueError("stack_count must be at least 1")
    if gap < 0:
        raise ValueError("gap must be zero or greater")

    width, depth, height = box_size(triangles)
    bed_width, bed_depth = bed_size
    per_flat_bed = copies_per_bed(width, depth, bed_width, bed_depth)
    if per_flat_bed < 1:
        raise ValueError("part footprint does not fit on the bed")

    stacks_needed = math.ceil(copies / stack_count)
    flat_beds = math.ceil(copies / per_flat_bed)
    stacked_beds = math.ceil(stacks_needed / per_flat_bed)
    stacked_height = stack_count * height + (stack_count - 1) * gap

    return BedAreaSavingsReport(
        copies=copies,
        stack_count=stack_count,
        copies_per_flat_bed=per_flat_bed,
        stacks_needed=stacks_needed,
        stacks_per_bed=per_flat_bed,
        flat_beds_needed=flat_beds,
        stacked_beds_needed=stacked_beds,
        bed_batch_savings=flat_beds - stacked_beds,
        stacked_height_mm=stacked_height,
    )


def quantize_xy(point: Point, precision: int) -> tuple[float, float]:
    return (round(point[0], precision), round(point[1], precision))


def triangle_components(
    faces: list[Triangle],
    precision: int,
) -> list[list[int]]:
    edge_to_faces: dict[tuple[tuple[float, float], tuple[float, float]], list[int]] = defaultdict(list)
    for index, tri in enumerate(faces):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            qa = quantize_xy(a, precision)
            qb = quantize_xy(b, precision)
            edge_to_faces[tuple(sorted((qa, qb)))].append(index)

    neighbors: dict[int, set[int]] = defaultdict(set)
    for indexes in edge_to_faces.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            neighbors[index].update(other for other in indexes if other != index)

    components: list[list[int]] = []
    seen: set[int] = set()
    for start in range(len(faces)):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        component: list[int] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in neighbors[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def classify_interface(
    area_ratio: float,
    component_count: int,
    largest_component_ratio: float,
) -> str:
    if area_ratio == 0:
        return "missing"
    if area_ratio < 0.05:
        return "tiny"
    if component_count > 8 or largest_component_ratio <= 0.50:
        return "fragmented"
    if area_ratio >= 0.50:
        return "broad"
    return "partial"


def analyze_interface_quality(
    triangles: list[Triangle],
    plane_z: float,
    tolerance: float,
    precision: int = 4,
) -> InterfaceQualityReport:
    mins, maxs = bounds(triangles)
    footprint_area = (maxs[0] - mins[0]) * (maxs[1] - mins[1])
    faces = plane_faces(triangles, plane_z, tolerance)
    total_area = sum(triangle_area_xy(face) for face in faces)
    components = triangle_components(faces, precision) if faces else []
    component_areas = [
        sum(triangle_area_xy(faces[index]) for index in component)
        for component in components
    ]
    largest_area = max(component_areas, default=0.0)
    area_ratio = total_area / footprint_area if footprint_area > 0 else 0.0
    largest_ratio = largest_area / total_area if total_area > 0 else 0.0

    return InterfaceQualityReport(
        plane_z=plane_z,
        classification=classify_interface(area_ratio, len(components), largest_ratio),
        face_count=len(faces),
        projected_area_mm2=total_area,
        footprint_coverage_ratio=area_ratio,
        component_count=len(components),
        largest_component_area_mm2=largest_area,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score STL files as candidates for vertical stack printing."
    )
    parser.add_argument("stls", nargs="+", type=Path)
    parser.add_argument("--copies", type=int, default=8)
    parser.add_argument("--stack-count", type=int, default=8)
    parser.add_argument("--gap", type=float, default=0.20)
    parser.add_argument("--bed-size", type=parse_bed_size, default=(256.0, 256.0))
    parser.add_argument(
        "--interface-plane",
        action="append",
        type=float,
        default=[],
        help="Z plane to inspect for separator quality. Defaults to model bottom and top.",
    )
    parser.add_argument("--tolerance", type=float, default=0.001)
    parser.add_argument("--precision", type=int, default=4)
    args = parser.parse_args()

    for stl in args.stls:
        triangles = read_binary_stl(stl)
        mins, maxs = bounds(triangles)
        interface_planes = args.interface_plane or [mins[2], maxs[2]]
        report = classify_stackability(triangles)
        savings = estimate_bed_area_savings(
            triangles,
            copies=args.copies,
            stack_count=args.stack_count,
            gap=args.gap,
            bed_size=args.bed_size,
        )
        print(stl)
        print(f"  stackability: {report.rating} ({report.stackability_score}/100)")
        print(f"  footprint area: {report.footprint_area_mm2:.2f} mm^2")
        print(f"  height: {report.height_mm:.2f} mm")
        print(f"  footprint/height ratio: {report.footprint_to_height_ratio:.2f}")
        print(
            f"  bed estimate: {savings.flat_beds_needed} flat bed batch(es) vs "
            f"{savings.stacked_beds_needed} stacked bed batch(es)"
        )
        print(f"  copies per flat bed: {savings.copies_per_flat_bed}")
        print(f"  stacks needed: {savings.stacks_needed}")
        print(f"  stacked height: {savings.stacked_height_mm:.2f} mm")
        print(f"  bed batch savings: {savings.bed_batch_savings}")
        for quality in interface_planes:
            interface = analyze_interface_quality(
                triangles,
                plane_z=quality,
                tolerance=args.tolerance,
                precision=args.precision,
            )
            print(
                f"  interface z={interface.plane_z:.4f}: {interface.classification}, "
                f"{interface.face_count} face(s), "
                f"{interface.footprint_coverage_ratio:.1%} footprint coverage, "
                f"{interface.component_count} component(s)"
            )
        for reason in report.reasons:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()

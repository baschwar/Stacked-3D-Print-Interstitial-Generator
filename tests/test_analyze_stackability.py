from __future__ import annotations

import unittest

from scripts.analyze_stackability import (
    analyze_interface_quality,
    classify_stackability,
    copies_per_bed,
    estimate_bed_area_savings,
)


def box_triangles(width: float, depth: float, height: float):
    p000 = (0.0, 0.0, 0.0)
    p100 = (width, 0.0, 0.0)
    p110 = (width, depth, 0.0)
    p010 = (0.0, depth, 0.0)
    p001 = (0.0, 0.0, height)
    p101 = (width, 0.0, height)
    p111 = (width, depth, height)
    p011 = (0.0, depth, height)
    return [
        (p000, p010, p110),
        (p000, p110, p100),
        (p001, p101, p111),
        (p001, p111, p011),
        (p000, p100, p101),
        (p000, p101, p001),
        (p100, p110, p111),
        (p100, p111, p101),
        (p110, p010, p011),
        (p110, p011, p111),
        (p010, p000, p001),
        (p010, p001, p011),
    ]


class StackabilityTests(unittest.TestCase):
    def test_scores_flat_broad_part_as_strong(self) -> None:
        report = classify_stackability(box_triangles(200, 200, 8))

        self.assertEqual(report.rating, "strong")
        self.assertGreaterEqual(report.stackability_score, 80)
        self.assertIn("large XY footprint relative to height", report.reasons)
        self.assertIn("broad flat top and bottom interface area", report.reasons)

    def test_scores_tall_small_part_as_weak(self) -> None:
        report = classify_stackability(box_triangles(20, 20, 80))

        self.assertEqual(report.rating, "weak")
        self.assertLess(report.stackability_score, 60)
        self.assertIn("small XY footprint relative to height", report.reasons)
        self.assertIn("tall part height", report.reasons)


class BedAreaSavingsTests(unittest.TestCase):
    def test_estimates_bed_batch_savings_for_low_plate(self) -> None:
        report = estimate_bed_area_savings(
            box_triangles(200, 200, 10),
            copies=8,
            stack_count=8,
            gap=0.2,
            bed_size=(256, 256),
        )

        self.assertEqual(report.copies_per_flat_bed, 1)
        self.assertEqual(report.flat_beds_needed, 8)
        self.assertEqual(report.stacked_beds_needed, 1)
        self.assertEqual(report.bed_batch_savings, 7)
        self.assertAlmostEqual(report.stacked_height_mm, 81.4)

    def test_copies_per_bed_considers_rotation(self) -> None:
        self.assertEqual(copies_per_bed(120, 80, 250, 180), 4)

    def test_rejects_parts_that_do_not_fit_bed(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not fit"):
            estimate_bed_area_savings(
                box_triangles(300, 300, 10),
                copies=2,
                stack_count=2,
                gap=0.2,
                bed_size=(256, 256),
            )


class InterfaceQualityTests(unittest.TestCase):
    def test_classifies_broad_box_interface(self) -> None:
        report = analyze_interface_quality(box_triangles(100, 100, 10), 10, tolerance=0.001)

        self.assertEqual(report.classification, "broad")
        self.assertEqual(report.face_count, 2)
        self.assertAlmostEqual(report.footprint_coverage_ratio, 1.0)
        self.assertEqual(report.component_count, 1)

    def test_classifies_tiny_interface(self) -> None:
        triangles = box_triangles(100, 100, 10)
        tiny = [((0.0, 0.0, 12.0), (10.0, 0.0, 12.0), (0.0, 10.0, 12.0))]
        report = analyze_interface_quality(triangles + tiny, 12, tolerance=0.001)

        self.assertEqual(report.classification, "tiny")
        self.assertEqual(report.face_count, 1)

    def test_classifies_fragmented_interface(self) -> None:
        triangles = box_triangles(100, 100, 10)
        island_a = ((0.0, 0.0, 12.0), (40.0, 0.0, 12.0), (0.0, 40.0, 12.0))
        island_b = ((60.0, 60.0, 12.0), (100.0, 60.0, 12.0), (60.0, 100.0, 12.0))
        report = analyze_interface_quality(triangles + [island_a, island_b], 12, tolerance=0.001)

        self.assertEqual(report.classification, "fragmented")
        self.assertEqual(report.component_count, 2)

    def test_classifies_missing_interface(self) -> None:
        report = analyze_interface_quality(box_triangles(100, 100, 10), 5, tolerance=0.001)

        self.assertEqual(report.classification, "missing")
        self.assertEqual(report.face_count, 0)


if __name__ == "__main__":
    unittest.main()

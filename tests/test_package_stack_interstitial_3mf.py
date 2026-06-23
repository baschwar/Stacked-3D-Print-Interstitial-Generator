from __future__ import annotations

import struct
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.package_stack_interstitial_3mf import write_3mf
from scripts.stl_utils import Triangle, normal_for


NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def write_test_stl(path: Path, triangles: list[Triangle]) -> None:
    with path.open("wb") as fh:
        fh.write(path.stem.encode("ascii")[:80].ljust(80, b" "))
        fh.write(struct.pack("<I", len(triangles)))
        for tri in triangles:
            fh.write(struct.pack("<fff", *normal_for(tri)))
            for vertex in tri:
                fh.write(struct.pack("<fff", *vertex))
            fh.write(struct.pack("<H", 0))


class PackageStackInterstitial3mfTests(unittest.TestCase):
    def test_packages_two_aligned_mesh_objects(self) -> None:
        stack_triangles = [((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0))]
        interstitial_triangles = [((0.0, 0.0, 1.0), (10.0, 0.0, 1.0), (0.0, 10.0, 1.0))]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stack = tmp_path / "stack.stl"
            interstitial = tmp_path / "interstitial.stl"
            output = tmp_path / "combined.3mf"
            write_test_stl(stack, stack_triangles)
            write_test_stl(interstitial, interstitial_triangles)

            write_3mf(output, stack, interstitial)

            with zipfile.ZipFile(output) as package:
                self.assertIn("[Content_Types].xml", package.namelist())
                self.assertIn("_rels/.rels", package.namelist())
                model = ET.fromstring(package.read("3D/3dmodel.model"))

            objects = model.findall("m:resources/m:object", NS)
            build_items = model.findall("m:build/m:item", NS)
            self.assertEqual(len(objects), 2)
            self.assertEqual(len(build_items), 2)
            self.assertEqual(objects[0].get("name"), "stack - stack")
            self.assertEqual(objects[1].get("name"), "interstitial - interstitial")


if __name__ == "__main__":
    unittest.main()


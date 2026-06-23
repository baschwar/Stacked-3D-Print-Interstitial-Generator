#!/usr/bin/env python3
"""Package an aligned stack STL and interstitial STL into one simple 3MF."""

from __future__ import annotations

import argparse
import html
import zipfile
from pathlib import Path

try:
    from stl_utils import Triangle, read_binary_stl
except ModuleNotFoundError:
    from scripts.stl_utils import Triangle, read_binary_stl


CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

ROOT_RELS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


def mesh_xml(triangles: list[Triangle]) -> str:
    vertex_ids: dict[tuple[float, float, float], int] = {}
    vertices: list[tuple[float, float, float]] = []
    triangle_indexes: list[tuple[int, int, int]] = []

    for tri in triangles:
        indexes = []
        for point in tri:
            key = (round(point[0], 6), round(point[1], 6), round(point[2], 6))
            if key not in vertex_ids:
                vertex_ids[key] = len(vertices)
                vertices.append(key)
            indexes.append(vertex_ids[key])
        triangle_indexes.append((indexes[0], indexes[1], indexes[2]))

    lines = ["   <mesh>", "    <vertices>"]
    for x, y, z in vertices:
        lines.append(f'     <vertex x="{fmt(x)}" y="{fmt(y)}" z="{fmt(z)}"/>')
    lines.append("    </vertices>")
    lines.append("    <triangles>")
    for v1, v2, v3 in triangle_indexes:
        lines.append(f'     <triangle v1="{v1}" v2="{v2}" v3="{v3}"/>')
    lines.append("    </triangles>")
    lines.append("   </mesh>")
    return "\n".join(lines)


def model_xml(stack_name: str, stack: list[Triangle], interstitial_name: str, interstitial: list[Triangle]) -> str:
    safe_stack_name = html.escape(stack_name, quote=True)
    safe_interstitial_name = html.escape(interstitial_name, quote=True)
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">',
            " <metadata name=\"Application\">Stacked 3D Print Interstitial Generator</metadata>",
            " <resources>",
            f'  <object id="1" type="model" name="{safe_stack_name}">',
            mesh_xml(stack),
            "  </object>",
            f'  <object id="2" type="model" name="{safe_interstitial_name}">',
            mesh_xml(interstitial),
            "  </object>",
            " </resources>",
            " <build>",
            '  <item objectid="1" printable="1"/>',
            '  <item objectid="2" printable="1"/>',
            " </build>",
            "</model>",
            "",
        ]
    )


def write_3mf(output: Path, stack_path: Path, interstitial_path: Path) -> None:
    stack = read_binary_stl(stack_path)
    interstitial = read_binary_stl(interstitial_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        package.writestr("_rels/.rels", ROOT_RELS_XML)
        package.writestr(
            "3D/3dmodel.model",
            model_xml(
                f"{stack_path.stem} - stack",
                stack,
                f"{interstitial_path.stem} - interstitial",
                interstitial,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package one stack STL and its aligned interstitial STL into one 3MF."
    )
    parser.add_argument("stack", type=Path)
    parser.add_argument("interstitial", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    output = args.output
    if output is None:
        output = args.stack.with_name(f"{args.stack.stem} - with interstitial.3mf")
    write_3mf(output, args.stack, args.interstitial)
    print(output)


if __name__ == "__main__":
    main()


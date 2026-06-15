# Stacked 3D Print Interstitial Generator

Generate STL stacks and aligned interstitial separator STLs for multi-material
stack printing experiments.

This project was built around a practical workflow: print repeated copies of a
part in one material, then add thin release/support-material layers between the
copies so the parts stay stable during printing but can separate afterward.

The scripts are dependency-free Python and currently support binary STL files.
They are not Gridfinity-specific; Gridfinity baseplates were the first real
test case, but the workflow is general.

## Current Sweet Spot

The current workflow is best suited to parts that already have broad, clean,
flat top and bottom surfaces or repeated horizontal interface planes. In those
cases, a thin aligned release/support-material interstitial can act like a
separator layer between copies without needing to invent much extra geometry.

Flat plates, trays, organizers, fixtures, baseplates, and simple mechanical
parts are natural candidates. More organic parts can still be stacked as STL
geometry, but the current interstitial generator may only find tiny contact
patches or no useful separator faces at all. A model like a Benchy is a good
stress test for the tooling, but it needs a different support strategy if the
goal is a practical print.

## Tools

- `scripts/stack_stls.py` creates repeated vertical stacks from one or more STL
  files.
- `scripts/generate_interstitials.py` extracts interface faces from an
  already-stacked STL and creates a separate aligned interstitial STL.
- `scripts/analyze_stackability.py` scores STL stackability, estimates bed-area
  savings, and reports separator interface quality before generating outputs.
- `scripts/inspect_stl_z.py` reports Z levels and coplanar face counts for STL
  validation.

## Basic Workflow

Create an 8-up stack with the first part normal and the remaining parts flipped:

```bash
python3 scripts/stack_stls.py input.stl \
  --copies 8 \
  --gap 0.20 \
  --flipped-after-first \
  --output-dir stacked-output
```

Generate interstitial layers for an already-stacked STL:

```bash
python3 scripts/generate_interstitials.py "stacked-output/input - 8up stack 0.20mm gap normal-then-flipped.stl" \
  --stack-count 8 \
  --first-interface-z 0.20 \
  --interface-step 4.40 \
  --thickness 0.20 \
  --output-dir interstitial-output
```

Import the original stack and the generated interstitial STL together in your
slicer. Keep them at the same origin, then assign the stack to the part material
and the interstitial STL to a release/support material such as Bambu Support PLA.

## Examples

The `examples/` folder includes a tiny synthetic frame generator:

```bash
python3 examples/make_demo_frame.py
python3 scripts/stack_stls.py examples/demo-frame.stl \
  --copies 4 \
  --gap 0.20 \
  --flipped-after-first
python3 scripts/generate_interstitials.py "stacked-output/demo-frame - 4up stack 0.20mm gap normal-then-flipped.stl" \
  --stack-count 4 \
  --first-interface-z 4.00 \
  --interface-step 4.20 \
  --thickness 0.20
```

It also includes full-size Gridfinity baseplate examples:

- `examples/gridfinity-baseplates/before/` contains already-stacked 8-up STL
  files.
- `examples/gridfinity-baseplates/after/` contains matching interstitial STL
  files generated from those stacks.

These are provided as real-world reference files. They are examples, not a
requirement. The scripts can read any suitable binary STL, but the current
separator workflow works best when the model has clean horizontal interface
geometry.

## Optional Edge Outset

If the separator does not fully support thin lips or corner regions, add a small
outset around the extracted interface boundaries:

```bash
python3 scripts/generate_interstitials.py stack.stl \
  --edge-outset 0.45
```

`0.45 mm` is roughly one nozzle width on many printers. Treat it as a test
value, not a universal default.

## Inspecting Z Levels

Use the inspector to confirm that a stack or interstitial STL has the expected
Z bands:

```bash
python3 scripts/inspect_stl_z.py interstitial-output/*.stl
```

You can also count horizontal faces at expected interface planes:

```bash
python3 scripts/inspect_stl_z.py stack.stl \
  --plane 0.20 \
  --plane 4.60 \
  --plane 9.00
```

## Analyzing Stackability

Use the analyzer before generating a stack when you want to know whether a part
is likely to benefit from vertical stacking:

```bash
python3 scripts/analyze_stackability.py input.stl \
  --copies 8 \
  --stack-count 8 \
  --bed-size 256x256
```

The report includes:

- A `strong`, `possible`, or `weak` stackability score.
- A simple bed-batch estimate comparing normal XY bed clones against vertical
  stacks.
- Interface quality reports for the model's bottom and top planes by default.

Inspect a specific separator plane with `--interface-plane`:

```bash
python3 scripts/analyze_stackability.py stacked.stl \
  --interface-plane 0.20 \
  --interface-plane 4.60
```

Interface quality is classified as `broad`, `partial`, `fragmented`, `tiny`, or
`missing` based on projected interface area and connected face regions.

## Slicer Notes

- Enable thin-wall detection when the part has one-wall lips or narrow edge
  features.
- Slow support/interface material paths and the first part-material layers after
  each interstitial.
- A brim or local anchor can help if a single corner still curls.
- STL does not store material assignments, so keep the stack and interstitials
  as separate aligned objects or package them in a slicer-native project file.

## Future Topics

The current project focuses on extracting thin separator layers from already
stacked geometry. Future experiments could make the workflow useful for a
broader range of shapes:

- **Stackability scoring:** report whether a part is a strong stacking
  candidate based on XY bed coverage, Z height, flat interface area, contact
  patch size, expected stack height, and likely stability.
- **Bed-area savings estimates:** compare printing a requested copy count as
  normal XY bed clones versus vertical stacks, so the tool can show when
  stacking is actually worth the added material and complexity.
- **Interface quality reports:** count horizontal faces at candidate separator
  planes and classify the result as broad, fragmented, tiny, or missing before
  generating an interstitial STL.
- **Footprint projection:** generate an expanded XY outline of the part for
  collision checks, support-table placement, bed-coverage estimates, and future
  nesting workflows.
- **Generated support tables:** compute the model's exterior XY footprint,
  expand it by a small clearance such as 1-2 mm, then generate an alternate
  material table with legs or walls around the part and a flat top plate above
  it. The next model could print on that artificial build surface without
  requiring the lower model to have a flat top.
- **Sacrificial carrier blocks:** generate a block or cradle from support
  material and subtract an offset version of the model from it. This could
  support awkward shapes, but would need release clearances and split lines to
  avoid mechanically locking around detailed geometry.
- **Footprint or silhouette separators:** derive support surfaces from projected
  XY silhouettes instead of only using existing coplanar mesh faces. This may
  help with parts that have uneven tops but a predictable outline.
- **Segmented release geometry:** split support structures into removable
  chunks, add seams, or keep material out of holes and undercuts so complex
  models can separate cleanly after printing.
- **Candidate use-case documentation:** expand the examples and guidance around
  low-profile batch parts such as baseplates, trays, fixture plates, shims,
  dividers, test coupons, flat brackets, lids, and spacer plates.
- **Slicer-native packaging:** emit 3MF or another slicer-friendly package that
  preserves aligned part/support objects and material assignments, instead of
  relying on separate STL imports.
- **Printability checks:** estimate support height, span length, clearance,
  contact area, and likely wobble before generating a stack that would be hard
  to print.

## Limitations

- Binary STL only.
- Units are assumed to be millimeters.
- The generator does not modify slicer settings or create G-code.
- The interstitial generator expects real coplanar interface faces at the Z
  planes you provide.
- Complex organic shapes, non-flat contact surfaces, or meshes without clean
  horizontal interface faces may need a different separator-generation strategy.

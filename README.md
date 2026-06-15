# Stacked 3D Print Interstitial Generator

Generate STL stacks and aligned interstitial separator STLs for multi-material
stack printing experiments.

This project was built around a practical workflow: print repeated copies of a
part in one material, then add thin release/support-material layers between the
copies so the parts stay stable during printing but can separate afterward.

The scripts are dependency-free Python and currently support binary STL files.
They are not Gridfinity-specific; Gridfinity baseplates were the first real
test case, but the workflow is general.

## Tools

- `scripts/stack_stls.py` creates repeated vertical stacks from one or more STL
  files.
- `scripts/generate_interstitials.py` extracts interface faces from an
  already-stacked STL and creates a separate aligned interstitial STL.
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
requirement; the scripts are intended to work with any suitable binary STL.

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

## Slicer Notes

- Enable thin-wall detection when the part has one-wall lips or narrow edge
  features.
- Slow support/interface material paths and the first part-material layers after
  each interstitial.
- A brim or local anchor can help if a single corner still curls.
- STL does not store material assignments, so keep the stack and interstitials
  as separate aligned objects or package them in a slicer-native project file.

## Limitations

- Binary STL only.
- Units are assumed to be millimeters.
- The generator does not modify slicer settings or create G-code.
- The interstitial generator expects real coplanar interface faces at the Z
  planes you provide.
- Complex organic shapes, non-flat contact surfaces, or meshes without clean
  horizontal interface faces may need a different separator-generation strategy.

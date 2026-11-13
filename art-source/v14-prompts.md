# v1.4.0 generated assets

Tool: built-in image_gen with genuine transparent background. Inputs were inspected before use. No API key or third-party image generator was used.

- `petkit-solo.png`: reproduce the provided white PETKIT FRESH ELEMENT SOLO feeder in a front three-quarter view, empty stainless bowl projecting left, correct proportions and vertical lettering; full isolated object, no cat, floor or shadow.
- `petkit-solo-se.png`: reproduce the provided frosted white PETKIT EVERSWEET SOLO SE, rounded-square tank, recessed top water tray, central small nozzle and green indicator; no tall faucet; full isolated transparent object.
- `fregate-food.png`: reproduce the inspected official red/gold/cream Fregate fresh-chicken baked cat-food bag; preserve the major brand, formula, gold cat outline pattern and lower cat illustration; one standing package, alpha background.
- `fregate-treat.png`: reproduce one red/gold Fregate 96:2:2 main-meal treat sachet, horizontally opened at left with a tiny paste tip, blue flavor stripe; no box, hand or cat.
- `equipment-care.png`: eight poses in a 4x2 grid using the existing golden cat as identity reference. Lower row is a stable standing drinking loop with small tongue changes. Original golden tail, no black tip, no equipment baked into sprites.
- `equipment-feed.png` (final feeding revision): four nearly identical grounded feeding poses in a 4x1 grid from the inspected first feeding pose. Nose and eyes at the same height, stable torso and paws, only tiny jaw/tongue motion. Nose approximately 40 logical pixels above ground; do not lower head farther. Keep round green-eyed head, photographic golden fur and original golden tail. No bowl, background, shadow or text.

The scratch cycle reuses the existing upright source row of `scratch-turn.png`; no new tail edits. Final assets are registered by `tools/prepare_v14_assets.py`, then offline encoded at 64 FPS with `tools/smooth_motion.py`.

Opposite-side revisions: `petkit-solo-reverse.png` has the bowl projecting RIGHT with normally readable FRESH ELEMENT SOLO / PETKIT lettering; `fregate-treat-reverse.png` is opened at RIGHT with normally readable Chinese/English printing. These are separately generated directions, not mirrored labels. Fountain uses its symmetric original image in either approach direction.

# Yuumi 1.3.1 — Scratcher Proportions

Goal: fix the demonstrated horizontal stretch and oversized garlic scratcher, while preserving natural rope/track contact and older releases.

1. Preserve the 413×768 artwork aspect ratio. Use a 132 logical-pixel total height at cat scale 1, about 80% of the low-scratch cat's visible height; derive width, track coordinates and placement from shared geometry.
2. Generate a low standing scratch cycle without props. Register the cat to its existing ground baseline and encode at 64 FPS. Do not shrink the cat to accommodate the toy.
3. Update rope and track contact anchors together. Enter reachable activities directly so replaying a nearby sitting activity does not force stand/walk/sit.
4. Test aspect preservation, scale factors 0.65/1/1.5, left/right contact, track bounds and native click/drag gestures. Inspect actual rendered before/after frames. Run the full suite and isolated packaged executable checks.
5. Bump to 1.3.1 and document the visual correction and further improvement suggestions. Publish a new commit/tag/Release, preserving v1.2.0 and v1.3.0 tags and exact asset hashes.

Appearance: preserve existing golden fur and tail; change the toy geometry and low scratching posture.

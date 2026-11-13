# Yuumi 1.4.0 equipment implementation plan

**Goal:** Correct the garlic scratcher to 1.2 times the visible seated cat and add verified PETKIT SOLO / SOLO SE equipment with Fregate food and treats.

**Architecture:** Keep the existing interruptible animation engine. Store independent feeder, fountain and treat objects in world coordinates; derive contact positions from asset geometry and keep all props uniformly scaled. Reuse existing care actions and add device feedback without runtime network access.

**Tech Stack:** Python, PySide6, generated transparent PNG assets, offline 64 FPS WebP cycles, PyInstaller.

1. Verify all four products with online image search and record exact model/source URLs. Hardware follows user reference photos; food uses the official red/gold fresh-chicken baked-food package and 96% main-meal treat wrapper as representative variants.
2. Generate transparent equipment/packaging assets, inspect alpha and identity, register geometry. Restore the existing upright scratching poses, preserving golden fur and tail. Encode the updated scratch and drinking cycle at 64 FPS.
3. Set scratcher height to 220 * 1.2 = 264 logical pixels (seated-cat visible alpha reference); preserve 413:768 aspect. Align front-paw contact in both directions and all user scales.
4. Add persistent independently draggable equipment, feed dispensing, visible kibble consumption, fountain ripples, refills and treat presentation. Stop preserves props; put away removes them; manual contact cancels pending goals.
5. Add meaningful regression checks for dimensions, contact geometry, refill/consumption, cancellation and native prop interaction. Run existing tests, native scene checks, standalone self-test and real-time action benchmarks.
6. Build versioned exe and actual-render preview, update README/version history and product-source notes. Publish a new tag/release and verify SHA256 assets while preserving v1.2.0, v1.3.0 and v1.3.1 unchanged.

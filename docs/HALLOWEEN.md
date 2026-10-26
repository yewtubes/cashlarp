# Halloween 2026

The seasonal logo was edited with the built-in image generator, using the original Cashlarp icon as its reference. `local/brand/halloween/icon-generated.png` is the generated transparent source; `icon.png` is its optimized UI version. `tools/build_halloween.py` packages light/dark SVG wordmarks and the favicon without changing default branding.

The pumpkins sit at the foot of the generated icon, forming one intentional brand lockup. No pumpkins float over page controls. Native surfaces receive a charcoal palette with warm readable text. Green native UI accents receive scoped orange CSS overrides; November removes the scope and restores the original styles. Native client bundles remain unchanged.

The server supplies UTC time. The one-time theme window closes November 1, 2026 at 00:00 UTC. Open tabs, sleeping tabs and fresh page loads restore default branding. Tests exercise the cutoff, native CSS accent restoration and the logo switch.

Image-generator prompt:

> Edit this Cashlarp app icon into a polished Halloween edition for a real web UI. Preserve the exact recognizable upright white double-stroke B symbol centered inside the rounded square. Change ALL green to vivid pumpkin orange (#FF7A18). Add a small black witch hat tilted over the upper left corner of the orange tile and two tiny stylized jack-o-lantern pumpkins sitting naturally at the foot of the tile, slightly overlapping its lower right edge. Premium simple flat graphic, crisp silhouettes, smooth clean outlines, bold readable at small size. Orange, near-black and white ONLY. Absolutely NO GREEN anywhere, no purple, no gradient background, no letters or wordmark, no scene, no cast shadow outside the icon. Genuinely transparent exterior background with generous transparent margins around the hat and pumpkins. The B glyph must remain complete, legible and unoccluded.

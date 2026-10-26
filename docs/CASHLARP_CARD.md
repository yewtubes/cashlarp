# Cashlarp Card artwork

The Cashlarp Card is a green theme in the original Card Studio catalog. Its
base artwork combines the Cashlarp mark with the Benjamin Netanyahu outline
stamp. The theme uses the native card renderer, chip, controls and drawing
layers. The original captured bundles and original ten theme records remain
unchanged. A small runtime adapter supplies the new card's background asset in the native 2D renderer and its 3D texture loader. Native personalization, chip and reverse-side layout are retained.

The sticker was generated with the built-in image generator and exported as
transparent black-outline art. It is vectorized into a normal SVG stamp so the
original editor can scale and place it. No colored portrait is used.

Files:

- `local/stamps/benjamin-netanyahu-source.png`: generated transparent source.
- `local/stamps/benjamin-netanyahu.svg`: monochrome SVG stamp.
- `local/stamps/benjamin-netanyahu.json`: native stamp catalog record.
- `local/card-themes/cashlarp.json`: native theme data.
- `local/card-themes/cashlarp-art.svg`: card background artwork.

To rebuild those checked-in artwork files, install Pillow in a development
environment and run `python3 tools/build_cashlarp_card.py`. Pillow is not a
runtime dependency.

Final image-generator prompt:

> Edit the Benjamin Netanyahu sticker just generated. Change its style
> completely to match the simple Cash App Card Studio black-outline stamps.
> Keep him recognizable: swept silver-hair shape, characteristic eyebrows,
> nose, jaw, head and shoulders, suit collar and tie. Use only clean pure BLACK
> contour line art on a genuinely TRANSPARENT background. NO skin tones, NO
> gray, NO green, NO color, NO gradients, NO hatching, NO shading, NO black-filled
> suit, NO white-filled silhouette, NO photographic detail, NO thick white
> sticker border. Sparse simplified vector-like outlines, rounded line caps and
> joins, consistent medium stroke weight, uncluttered facial features, readable
> at a 50 by 50 pixel stamp size. All enclosed areas must remain transparent.
> One centered portrait stamp, generous transparent margins, no text or other
> objects.

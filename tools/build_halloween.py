"""Package the image-generated orange Halloween logo; Pillow is build-only."""
from pathlib import Path
import base64
from PIL import Image

root=Path(__file__).resolve().parents[1]/'local/brand/halloween'
source=Image.open(root/'icon-generated.png').convert('RGBA')
source=source.crop(source.getbbox())
source.thumbnail((256,256),Image.Resampling.LANCZOS)
source.save(root/'icon.png',optimize=True)
data=base64.b64encode((root/'icon.png').read_bytes()).decode()
for suffix,color in [('', '#C74E00'),('-dark','#FF9A45')]:
 svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="560" height="160" viewBox="0 0 560 160" role="img" aria-label="Cashlarp Halloween"><image x="0" y="0" width="152" height="160" href="data:image/png;base64,{data}"/><text x="161" y="110" font-family="Arial,Helvetica,sans-serif" font-size="88" font-weight="900" letter-spacing="-4" fill="{color}">Cashlarp</text></svg>'''
 (root/('cashlarp-wordmark'+suffix+'.svg')).write_text(svg+'\n')
(root/'favicon.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><image width="256" height="256" href="data:image/png;base64,{data}"/></svg>\n')
print('Packaged generated orange icon, light/dark wordmarks and favicon')

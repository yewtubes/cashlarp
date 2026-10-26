#!/usr/bin/env python3
"""Vectorize the image-generated outline stamp and package the Cashlarp card art.

Pillow is needed only to rebuild these checked-in artwork files, not at runtime.
"""
from pathlib import Path
from collections import defaultdict
import base64
import json
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
source=Image.open(ROOT/'local/stamps/benjamin-netanyahu-source.png').convert('RGBA')
source.thumbnail((512,512),Image.Resampling.LANCZOS)
canvas=Image.new('RGBA',(512,512));canvas.alpha_composite(source,((512-source.width)//2,(512-source.height)//2))
pixels=canvas.load()
black={(x,y) for y in range(512) for x in range(512) if pixels[x,y][3]>=100 and sum(pixels[x,y][:3])<384}
edges=defaultdict(list)
for x,y in black:
 if (x,y-1) not in black:edges[x,y].append((x+1,y))
 if (x+1,y) not in black:edges[x+1,y].append((x+1,y+1))
 if (x,y+1) not in black:edges[x+1,y+1].append((x,y+1))
 if (x-1,y) not in black:edges[x,y+1].append((x,y))
paths=[]
while edges:
 start=next(iter(edges));point=start;polygon=[start]
 while point in edges:
  following=edges[point].pop()
  if not edges[point]:del edges[point]
  polygon.append(following);point=following
  if point==start:break
 if len(polygon)<5:continue
 simple=[]
 for p in polygon:
  while len(simple)>1 and (simple[-1][0]-simple[-2][0])*(p[1]-simple[-1][1])==(simple[-1][1]-simple[-2][1])*(p[0]-simple[-1][0]):simple.pop()
  simple.append(p)
 coords=[(round(x*50/512,3),round(y*50/512,3)) for x,y in simple]
 paths.append('M'+'L'.join(f'{x},{y}' for x,y in coords)+'Z')
shape='<path fill="#000000" fill-rule="evenodd" d="'+''.join(paths)+'"/>'
stamp='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50">'+shape+'</svg>'
(ROOT/'local/stamps/benjamin-netanyahu.svg').write_text(stamp+'\n')
(ROOT/'local/stamps/benjamin-netanyahu.json').write_text(json.dumps({'name':'cashlarp_netanyahu','accessibility_text':'Benjamin Netanyahu outline','svg':stamp,'min_scale':80},indent=2)+'\n')
logo=base64.b64encode((ROOT/'local/brand/favicon.png').read_bytes()).decode()
art='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 640"><image x="230" y="48" width="64" height="64" href="data:image/png;base64,'+logo+'"/><text x="310" y="104" font-family="Arial,Helvetica,sans-serif" font-weight="900" font-size="60" letter-spacing="-3" fill="#052b14">Cashlarp</text><g transform="translate(575 176) scale(7.3)">'+shape+'</g><text x="62" y="590" font-family="Arial,Helvetica,sans-serif" font-size="20" letter-spacing="3" fill="#052b14">CASHLARP CARD</text></svg>'
(ROOT/'local/card-themes/cashlarp-art.svg').write_text(art+'\n')
theme={'token':'CT_CASHLARP','title':'Cashlarp Card','id':'CASHLARP','card_color':'#00D64B','ink_color':'#052B14','card_info_text_color':'#052B14','mag_stripe_color':'#063A1D','font':'CASH_MARKET_REGULAR','gradient_style':'DIAGONAL_DARK','pattern_grid_alpha':0.15,'card_customization_margin':{'color':'#00D64B','alpha':0.0,'size':0.0}}
(ROOT/'local/card-themes/cashlarp.json').write_text(json.dumps(theme,indent=2)+'\n')
print('Built monochrome outline stamp and Cashlarp card texture from image-generated artwork')

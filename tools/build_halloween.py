"""Rebuild transparent Halloween SVGs from the original Cashlarp branding."""
from pathlib import Path
import base64
root=Path(__file__).resolve().parents[1]/'local/brand'
(root/'halloween').mkdir(exist_ok=True)
pumpkin='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" fill="none"><path d="M79 40q-5-19 9-28l12 9q-15 7-12 21" fill="#00D64B"/><path d="M81 44c-52-30-82 8-65 62 12 38 40 39 65 31 30 13 63-6 65-40 4-47-28-68-65-53Z" fill="#FF8A24" stroke="#161215" stroke-width="5"/><path d="M68 44c-28 17-32 73 5 95M94 44c26 22 24 73-7 95" stroke="#161215" stroke-width="4" opacity=".32"/><path d="m38 84 20-18 12 22Zm53 4 12-22 21 18ZM42 105l21 7 6-8 10 13 12-13 9 8 20-7-18 24H61Z" fill="#161215"/></svg>'''
(root/'halloween/pumpkin.svg').write_text(pumpkin+'\n')
hat='''<g stroke="#161215" stroke-width="3" stroke-linejoin="round"><path d="m18 34 32-30 8 17 28 21Z" fill="#242025"/><path d="m27 27 39 4 8 8-53-4Z" fill="#FF8A24"/><path d="M5 36q47-9 93 9-49 13-93-9Z" fill="#242025"/><path d="m48 28 12 2-1 7-12-2Z" fill="#00D64B"/></g>'''
bat='<path d="m372 19 9 5 4-9 5 9 9-5 8 12-13-1-9 7-9-7-13 1Z" fill="#FF8A24"/>'
for suffix in ['', '-dark']:
 s=(root/('cashlarp-wordmark'+suffix+'.svg')).read_text()
 start=s.index('<svg x=');end=s.index('</svg>',start)+6
 icon=base64.b64encode((root/'favicon.png').read_bytes()).decode()
 s=s[:start]+'<image x="7" y="23" width="90" height="88" href="data:image/png;base64,'+icon+'"/>'+s[end:]
 s=s.replace('fill="#000">Cashlarp','fill="#E86C13">Cashlarp').replace('fill="#fff">Cashlarp','fill="#FFAB59">Cashlarp')
 i=s.rfind('</svg>');s=s[:i]+hat+bat+s[i:]
 (root/('halloween/cashlarp-wordmark'+suffix+'.svg')).write_text(s)
(root/'halloween/favicon.svg').write_text(pumpkin+'\n')

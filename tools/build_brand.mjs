// Embed the selected opaque generated art inside an exterior-only SVG clip.
// The bitmap stays untouched; the web asset has transparent space outside it.
import {readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const png=readFileSync(resolve(root,'local/brand/cashlarp-icon-source.png')).toString('base64');
const tile=`<svg x="0" y="0" width="112" height="112" viewBox="65 77 1123 1101"><defs><clipPath id="tile"><rect x="65" y="77" width="1123" height="1101" rx="245"/></clipPath></defs><image width="1254" height="1254" href="data:image/png;base64,${png}" clip-path="url(#tile)"/></svg>`;
writeFileSync(resolve(root,'local/brand/cashlarp-icon.svg'),`<svg xmlns="http://www.w3.org/2000/svg" width="112" height="112" viewBox="0 0 112 112" role="img" aria-label="Cashlarp">${tile}</svg>`);
writeFileSync(resolve(root,'local/brand/cashlarp-wordmark.svg'),`<svg xmlns="http://www.w3.org/2000/svg" width="470" height="112" viewBox="0 0 470 112" role="img" aria-label="Cashlarp">${tile}<text x="129" y="84" font-family="Arial,Helvetica,sans-serif" font-size="80" font-weight="900" letter-spacing="-4" fill="#000">Cashlarp</text></svg>`);
console.log('Built Cashlarp web logos with opaque art and transparent exterior');
const wordmark=readFileSync(resolve(root,'local/brand/cashlarp-wordmark.svg'),'utf8');
writeFileSync(resolve(root,'local/brand/cashlarp-wordmark-dark.svg'),wordmark.replace('fill="#000"','fill="#fff"'));

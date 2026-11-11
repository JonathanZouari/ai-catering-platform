// Static review artifact, generated from the same schema descriptors as the admin explorer.
import {writeFile} from 'node:fs/promises';
import {TABLES, RELATIONS} from '../frontend/admin/js/schema.js';

const columns = [
  ['customers','addresses','events'],
  ['orders','order_items','order_submissions'],
  ['dish_categories','dishes','dish_dietary'],
  ['allergens','dish_allergens','delivery_zones','time_slots','blocked_dates'],
  ['ai_conversations','ai_messages','ai_change_proposals'],
];
const box = new Map();
const width=350, gap=75, line=22;
for(const [col,names] of columns.entries()) {
  let y=125;
  for(const name of names) {
    const table=TABLES.find(t=>t.name===name);
    if(!table) throw new Error(`Missing schema descriptor: ${name}`);
    const height=76+table.columns.length*line;
    box.set(name,{x:40+col*(width+gap),y,width,height,table});
    y+=height+48;
  }
}
if(box.size!==TABLES.length) throw new Error('Diagram does not cover every table');
const W=columns.length*(width+gap)+5;
const H=Math.max(...[...box.values()].map(b=>b.y+b.height))+90;
const xml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const parts=[`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<style>text{font-family:Arial,sans-serif}.code{font-family:Consolas,monospace}</style>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#64748b"/></marker></defs>
<rect width="100%" height="100%" fill="#f1f5f9"/>
<text x="40" y="42" font-size="28" font-weight="bold" fill="#0f172a">yumm.ai — reviewed MVP schema</text>
<text x="40" y="72" font-size="17" fill="#475569">17 public tables · bigint domain keys · FK arrows point to the referenced table · schema foundation, not a live cloud screenshot</text>
<text x="40" y="98" font-size="15" fill="#475569">PK primary key | FK foreign key | AI records and submission credentials: server only | operations extension excluded</text>`];
for(const [i,r] of RELATIONS.entries()) {
  const from=box.get(r.from),to=box.get(r.to);
  const right=from.x<=to.x;
  const x1=from.x+(right?width:0),x2=to.x+(right?0:width);
  const idx=Math.max(0,from.table.columns.findIndex(c=>c.name===r.columns[0]));
  const y1=from.y+68+idx*line,y2=to.y+32;
  const mid=from.x===to.x?from.x+width+20+(i%3)*8:(x1+x2)/2+(i%3)*7;
  parts.push(`<path d="M${x1},${y1} H${mid} V${y2} H${x2}" fill="none" stroke="#94a3b8" stroke-width="1.5" opacity="0.7" marker-end="url(#arrow)"/>`);
}
for(const {x,y,height,table} of box.values()) {
  parts.push(`<rect x="${x}" y="${y}" width="${width}" height="${height}" rx="9" fill="white" stroke="#cbd5e1"/>
<rect x="${x}" y="${y}" width="${width}" height="45" rx="9" fill="${table.hiddenFromData?'#334155':'#0f766e'}"/>
<text class="code" x="${x+14}" y="${y+29}" font-size="19" font-weight="bold" fill="white">${xml(table.name)}</text>`);
  for(const [i,c] of table.columns.entries()) {
    const tags=[c.pk?'PK':'',c.fk?'FK':''].filter(Boolean).join('/');
    parts.push(`<text class="code" x="${x+13}" y="${y+69+i*line}" font-size="14" fill="${c.pk?'#0f766e':'#334155'}">${xml(c.name)}${tags?' ['+tags+']':''}${c.nullable?' ?':''}</text>`);
  }
}
parts.push(`<text x="40" y="${H-25}" font-size="16" fill="#475569">Allergen status: contains / free / unknown. Missing data is unknown. Prices have one canonical source; order lines retain receipt snapshots.</text></svg>`);
await writeFile(new URL('../docs/catering-schema.svg',import.meta.url),parts.join('\n'));
console.log(`Generated ${TABLES.length} tables and ${RELATIONS.length} FK connections.`);

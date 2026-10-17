// Preserved comparison that rejected fresh UTC timestamps after the successful probe.
import fs from 'node:fs';
const original=fs.readFileSync('.runtime/storyboard-director-origin/startup-probe.json','utf8');
const recheck=fs.readFileSync('docs/delivery/v2-development/storyboard-director-20261017/inventory/recheck-startup.json','utf8');
if(recheck!==original)throw Error('proof differs');

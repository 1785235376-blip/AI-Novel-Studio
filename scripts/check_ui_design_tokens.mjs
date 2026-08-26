import fs from 'node:fs';import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');const tokenFile=path.join(root,'frontend','src','ui','tokens.css');const allowed=new Set([tokenFile]);const files=[];
function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const full=path.join(dir,entry.name);if(entry.isDirectory())walk(full);else if(/\.(css|tsx)$/.test(entry.name))files.push(full)}}walk(path.join(root,'frontend','src','ui'));
const violations=[];for(const file of files){if(allowed.has(file))continue;const text=fs.readFileSync(file,'utf8');for(const [index,line] of text.split(/\r?\n/).entries())if(/#[0-9a-f]{3,8}\b|\brgb\(|\bhsl\(/i.test(line))violations.push(`${path.relative(root,file)}:${index+1}`)}
if(violations.length){console.error(`Raw UI colors outside tokens:\n${violations.join('\n')}`);process.exit(1)}console.log(`UI token guard PASS (${files.length} files)`);

// Cross-owner test bridge only. Calls the product helper; never an execution engine.
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),front=path.join(root,'frontend'),req=Module.createRequire(path.join(front,'package.json')),esbuild=Module.createRequire(req.resolve('vite'))('esbuild');
const built=esbuild.buildSync({stdin:{contents:`export {captureCanvasImageTask,replaceCanvasImageTaskResult} from './src/creative/canvasImageTask';`,resolveDir:front,loader:'ts'},bundle:true,platform:'node',format:'cjs',write:false,metafile:true});
const filename=path.join(path.dirname(process.argv[3]),'virtual-task-adoption.cjs'),loaded=new Module(filename,module);loaded.filename=filename;loaded._compile(built.outputFiles[0].text,filename);
const value=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),origin=loaded.exports.captureCanvasImageTask(value.canvas,'origin-card',value.source),definition=loaded.exports.replaceCanvasImageTaskResult(origin,value.canvas,value.approved,value.asset);
fs.writeFileSync(process.argv[3],JSON.stringify({origin,definition},null,2)+'\n');
fs.writeFileSync(path.join(path.dirname(process.argv[3]),'task-adoption-source-bindings.json'),JSON.stringify({files:Object.keys(built.metafile.inputs).filter(p=>p!=='<stdin>').map(p=>({path:path.relative(root,path.resolve(p)).replaceAll('\\','/'),sha256:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')}))},null,2)+'\n');

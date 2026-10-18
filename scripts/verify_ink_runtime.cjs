// Test-only pinned target harness. Never shipped/executed by the product.
const fs = require('fs');
const path = require('path');
const root = process.env.POEMSEED_INKJS_ROOT;
if (!root || JSON.parse(fs.readFileSync(path.join(root, 'package.json'))).version !== '2.3.2') throw Error('PIN_REQUIRED');
const crypto = require('crypto');
if (crypto.createHash('sha256').update(fs.readFileSync(path.join(root, 'dist/ink-full.js'))).digest('hex') !== '4a76187c713c889b5e71d9380b37b5b42eaba9d24af099bb9f968d02311cfeef') throw Error('RUNTIME_INTEGRITY_MISMATCH');
const {Compiler, Story} = require(path.join(root, 'dist/ink-full.js'));
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = cases.map(item => {
  let fileCalls = 0;
  const deny = () => { fileCalls++; throw Error('FILE_ACCESS_DENIED'); };
  const errors = [];
  const compiler = new Compiler(item.source, {errorHandler: (message, type) => errors.push({message,type}),
    fileHandler: {ResolveInkFilename: deny, LoadInkFileContents: deny}});
  let story; try { story = compiler.Compile(); } catch(e) { console.error(JSON.stringify(errors)); process.exit(2); }
  const compiled = story.ToJson();
  const snapshots = [];
  const advance = () => {
    let output = '', ticks = 0;
    while (story.canContinue) { if (++ticks > 1000) throw Error('CONTINUE_CAP'); output += story.Continue(); }
    if (story.hasError) throw Error(JSON.stringify(story.currentErrors));
    const values = Object.fromEntries(item.variables.map(n => [n, story.variablesState.$(n)]));
    snapshots.push({output, choices:story.currentChoices.map(c=>c.text), values,
      node:story.variablesState.$('ans_node'), steps:story.variablesState.$('ans_steps'), status:story.variablesState.$('ans_status')});
    // Actual target serialization/reconstruction at every step.
    const saved = story.state.ToJson(); const restarted = new Story(compiled); restarted.state.LoadJson(saved); story = restarted;
  };
  advance();
  for (const index of item.indices) { story.ChooseChoiceIndex(index); advance(); }
  if(fileCalls || errors.length) throw Error(JSON.stringify({fileCalls, errors}));
  return {snapshots, fileCalls, errors, version:'2.3.2'};
});
process.stdout.write(JSON.stringify(results));

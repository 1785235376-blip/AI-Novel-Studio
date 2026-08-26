import {execFileSync} from 'node:child_process';
import path from 'node:path';

export default async function globalTeardown() {
  const root = path.resolve(__dirname, '..', '..');
  execFileSync(path.join(root, '.venv', 'Scripts', 'python.exe'), [path.join(__dirname, 'database_fixture.py'), 'cleanup'], {stdio: 'inherit'});
}

// @vitest-environment jsdom
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {useState} from 'react';
import {act, cleanup, fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext} from '../api';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {AppShell, type StudioModule} from './AppShell';
import {FeatureLauncher, FEATURE_GROUP_DEFAULTS} from './FeatureLauncher';
import {LocalAiDiscovery} from './LocalAiDiscovery';
import {ModuleWorkspaceRoutes} from './ModuleWorkspaceRoutes';

// Leave routing, AppShell, ModuleSwitcher and FeatureLauncher real. Their
// unrelated panel bodies do not need provider/configuration HTTP for this check.
vi.mock('./AiControlCenter', () => ({AiControlCenter: () => null}));
vi.mock('./CapabilityStatusCenter', () => ({CapabilityStatusCenter: () => null}));

const filesJourney = readFileSync(resolve(process.cwd(), 'tests/e2e/v2-local-ai-files-live.spec.ts'), 'utf8');
const legacyJourney = readFileSync(resolve(process.cwd(), 'tests/e2e/v2-local-ai-legacy-host-live.spec.ts'), 'utf8');
const fetchMock = vi.fn();
const context = {sessionToken: ''};
const scope = {workspace: 'fixture', project: 'fixture', storyline: '', branch: ''};
const completed = {
  scan: {id: 'preserved-completed-scan', status: 'COMPLETED', runtimes: [], candidates: [], errors: [],
    environment_schema_version: 2, model_files: [], roots: []},
  registrations: [], settings: {scan_roots: [], runtimes: [], include_common_model_dirs: false},
  hardware: {cpu: 'preserved-fixture-cpu', gpus: []},
};

function ExistingModuleRoutes() {
  const [module, setModule] = useState<StudioModule>('CONTROL');
  const [groups, setGroups] = useState(FEATURE_GROUP_DEFAULTS);
  if (module !== 'NOVEL') return <ModuleWorkspaceRoutes module={module} onModuleChange={setModule} scope={scope} actor="fixture"/>;
  return <AppShell module={module} onModuleChange={setModule} scope={scope} actor="fixture"
    sidebar={<FeatureLauncher selectedId="agents" expandedGroups={groups} onSelect={() => {}}
      onToggleGroup={id => setGroups(current => ({...current, [id]: !current[id]}))}/>}
    main={null} inspector={null} status={null}/>;
}

beforeEach(() => {
  setCollaborationContext(context);
  useStudio.setState({sessionToken: '', novelId: 'fixture', actor: undefined, scope: undefined});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  bindLocalHostSession('fixture-host', {session_mode: 'LOCAL_HOST', actor_id: 'fixture'});
  fetchMock.mockReset().mockImplementation(async () => new Response(JSON.stringify(completed)));
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  setCollaborationContext(context);
  useStudio.setState({sessionToken: '', novelId: '', actor: undefined, scope: undefined});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
});

describe('additive M3 browser journeys follow existing product state', () => {
  it('uses the exact existing rescan action after recovering the prior completed scan', async () => {
    render(<LocalAiDiscovery canMutate onboarding={{context, projectId: 'fixture'}}/>);
    // The initial disabled label is transient, matching the hosted failure log.
    expect((screen.getByRole('button', {name: '预览 AI 检测范围'}) as HTMLButtonElement).disabled).toBe(true);
    await screen.findByText('COMPLETED', {exact: true});
    const currentAction = screen.getByRole('button', {name: '重新预览检测范围'}) as HTMLButtonElement;
    expect(currentAction.disabled).toBe(false);
    expect(screen.queryByRole('button', {name: '预览 AI 检测范围'})).toBeNull();
    expect(screen.getByText('preserved-fixture-cpu')).toBeTruthy();
    expect(fetchMock.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
    // Both the browser's enabled assertion and subsequent click must target the
    // recovered state. Keep the completed-scan prerequisite and exact matching.
    expect(filesJourney).toContain("expect(before.scan_status).toBe('COMPLETED')");
    const names = [...filesJourney.matchAll(/getByRole\('button',\s*\{name:\s*'([^']*预览[^']*)',\s*exact:\s*true\}/g)].map(match => match[1]);
    expect(names).toHaveLength(2);
    for (const name of names) expect(screen.queryByRole('button', {name})).toBe(currentAction);
  });

  it('restores the same completed observation after host rebind without a new scan', async () => {
    render(<LocalAiDiscovery canMutate onboarding={{context, projectId: 'fixture'}}/>);
    await screen.findByText('COMPLETED', {exact: true});
    act(() => {clearLocalHostSession(); bindLocalHostSession('fixture-host', {session_mode: 'LOCAL_HOST', actor_id: 'fixture'});});
    await screen.findByText('COMPLETED', {exact: true});
    expect(screen.getByText('preserved-fixture-cpu')).toBeTruthy();
    expect((screen.getByRole('button', {name: '重新预览检测范围'}) as HTMLButtonElement).disabled).toBe(false);
    expect(fetchMock.mock.calls.every(([, init]) => init.method === 'GET' && init.headers['X-Session-Token'] === 'fixture-host')).toBe(true);
  });

  it.each([
    ['files reload', filesJourney, 'bindHostAndOpenModels'],
    ['legacy revoked-host rebind', legacyJourney, 'bindAndOpen'],
  ])('returns from CONTROL through the existing NOVEL tab before opening feature navigation: %s', (_name, journey, helper) => {
    render(<ExistingModuleRoutes/>);
    expect(screen.getByRole('tablist', {name: '主控设置'})).toBeTruthy();
    expect(screen.queryByRole('button', {name: '打开功能导航'})).toBeNull();
    fireEvent.click(within(screen.getByRole('tablist', {name: '创作模块'})).getByRole('tab', {name: '小说'}));
    expect(screen.queryByRole('tablist', {name: '主控设置'})).toBeNull();
    fireEvent.click(screen.getByRole('button', {name: '打开功能导航'}));
    expect(within(screen.getByRole('navigation', {name: '功能面板导航'})).getByRole('button', {name: 'Agent 团队'})).toBeTruthy();

    // Guard the actual browser helper, rather than just proving a separate
    // successful test path. These source checks preserve its real UI entry.
    const start = journey.indexOf(`async function ${helper}(`);
    expect(start).toBeGreaterThanOrEqual(0);
    const prefix = journey.slice(start, journey.indexOf('const navigation =', start));
    expect(prefix).toContain("getByRole('tablist', {name: '创作模块', exact: true}).getByRole('tab', {name: '小说', exact: true}).click()");
    expect(prefix.indexOf("name: '小说'")).toBeLessThan(prefix.indexOf("name: '打开功能导航'"));
  });
});

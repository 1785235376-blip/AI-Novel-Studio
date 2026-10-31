/**
 * UX-07 只读控制器。
 *
 * 状态机是显式的七值：`IDLE | LOADING | READY | EMPTY | PARTIAL | DENIED | FAILED`。
 * 关键约定（由测试断言）：
 * - 被拒绝的读取 → `DENIED`；**永不**渲染成 `EMPTY`（"没有可用模型"）。
 * - `EMPTY` 只表示"原 owner 成功返回、但注册表确实是空的"。
 * - 读取失败 → `FAILED`，并保留上一次成功读取的值（如果存在）供对照。
 * - 没有定时器、没有自动重试、没有自动下载/恢复。每次读取都由显式的 `reload()` 触发。
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { getLocale, tz } from '../i18n'; // [HERMIA-FE-20261025 VERA-097 P3]
import type { StudioGraphTransport } from '../creative/studioGraphClient';
import type { CollaborationContext } from '../api';
import { createModelCenterClient, type ModelCenterClient, type ModelCenterSourceStatus } from './modelCenterClient';
import { modelCenterInjectedCatalog, modelCenterStorage } from './modelCenterContract';
import {
  MODEL_CENTER_CODES,
  type ModelCenterCatalogPayload, type ModelCenterCredentialState, type ModelCenterHardwareFact,
  type ModelCenterStoragePayload, type ModelCenterSurfaceState,
} from './modelCenterTypes';

export type ModelCenterProblem = { code: string; message: string };

export type ModelCenterControllerProps = {
  projectId: string;
  transport: StudioGraphTransport;
  scope?: CollaborationContext['scope'];
  /** 稳定的工作区/分支身份；变化会丢弃此前读到的一切。 */
  identity: string;
  /** 视图在屏幕上。关闭时永不读取。 */
  active: boolean;
  denied: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(w: () => Promise<T>) => Promise<T>;
  /** 预留给未来的写操作；本面板当前**没有任何**写操作。 */
  mutate: <T>(w: () => Promise<T>) => Promise<T>;
  /** 已经解码的只读事实（调用方注入）；提供后即不再从端点读取该来源。 */
  catalog?: unknown;
  storage?: unknown;
  hardware?: unknown;
  onUnavailable?: () => void;
};

/** 文案里出现路径、端点或凭据迹象时，一律回退到本模块自己的固定文案。 */
const UNSAFE_MESSAGE = /[A-Za-z]:\\|\/(?:home|mnt|tmp|var|usr)\/|https?:\/\/|sk-[A-Za-z0-9]|bearer|api[_-]?key|secret|token|password/i;
/**
 * owner 文案只在它"确实像本地化用户文案"时透传：
 * 必须有界、无控制字符、不含路径/端点/凭据迹象，且含中日韩文字
 * （纯 ASCII 的英文诊断串通常带内部标识，按不透明处理）。
 */
function ownerMessage(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const message = value.trim();
  if (!message || message.length > 240 || /[\u0000-\u001f\u007f]/.test(message)) return undefined;
  if (UNSAFE_MESSAGE.test(message)) return undefined;
  if (!/[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/.test(message)) return undefined;
  return message;
}

function problemOf(reason: unknown, fallback: string): ModelCenterProblem {
  if (reason instanceof ApiError) {
    // 请求 id 与 owner 的英文诊断串都不进入界面；无法安全透传时用本模块的固定文案。
    // [HERMIA-FE-20261025 VERA-097 P3] 英文界面不透传中文 owner 文案；固定文案按当前语言（tz 反查字典）
    return { code: reason.problem.code, message: (getLocale() === 'en' ? undefined : ownerMessage(reason.problem.message)) ?? tz(fallback) };
  }
  // 非 ApiError 的本地异常文案永不原样渲染。
  return { code: MODEL_CENTER_CODES.readFailed.code, message: tz(fallback) };
}

export function useModelCenter(props: ModelCenterControllerProps) {
  const [state, setState] = useState<ModelCenterSurfaceState>(props.denied ? 'DENIED' : 'IDLE');
  const [problem, setProblem] = useState<ModelCenterProblem>();
  const [catalog, setCatalog] = useState<ModelCenterCatalogPayload>();
  const [storage, setStorage] = useState<ModelCenterStoragePayload>();
  const [credentials, setCredentials] = useState<readonly ModelCenterCredentialState[]>([]);
  /** 每个来源各自的状态：一个来源失败不会让另一个来源的事实消失。 */
  const [sources, setSources] = useState<{ catalog: ModelCenterSourceStatus; storage: ModelCenterSourceStatus }>({
    catalog: { state: 'UNAVAILABLE', code: MODEL_CENTER_CODES.catalogUnavailable.code },
    storage: { state: 'UNAVAILABLE', code: MODEL_CENTER_CODES.catalogUnavailable.code },
  });
  const [hardware, setHardware] = useState<ModelCenterHardwareFact>({ state: 'UNKNOWN', reason: MODEL_CENTER_CODES.hardwareUnavailable.code });
  const [selected, setSelected] = useState<string>();

  const alive = useRef(true), epoch = useRef(0), pending = useRef(false), revoked = useRef(false);
  const abort = useRef<AbortController>(), latest = useRef(props);
  latest.current = props;

  const client = useRef<ModelCenterClient>();
  try { client.current = createModelCenterClient(props.projectId, props.transport, props.scope); }
  catch { client.current = undefined; }

  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; abort.current?.abort(); }; }, []);

  const admit = useCallback(() => alive.current && !revoked.current && latest.current.active
    && !latest.current.denied && latest.current.isCurrent(), []);

  useEffect(() => {
    epoch.current++; abort.current?.abort(); pending.current = false;
    revoked.current = props.denied;
    setCatalog(undefined); setStorage(undefined); setCredentials([]); setSelected(undefined); setProblem(undefined);
    setSources({
      catalog: { state: 'UNAVAILABLE', code: MODEL_CENTER_CODES.catalogUnavailable.code },
      storage: { state: 'UNAVAILABLE', code: MODEL_CENTER_CODES.catalogUnavailable.code },
    });
    setState(props.denied ? 'DENIED' : 'IDLE');
  }, [props.identity, props.denied]);

  const reload = useCallback(async () => {
    const captured = latest.current;
    if (!admit() || pending.current || captured.busy) return;
    const controller = new AbortController();
    abort.current?.abort(); abort.current = controller;
    const request = ++epoch.current;
    pending.current = true; setProblem(undefined); setState('LOADING');
    try {
      // Injected facts cannot bypass the same project-context boundary used
      // when the original client performs its own read.
      if (!client.current) throw new ApiError({ status: 400, code: MODEL_CENTER_CODES.catalogInvalid.code, message: MODEL_CENTER_CODES.catalogInvalid.message });
      if (captured.scope && captured.scope.projectId !== captured.projectId) throw new ApiError({ status: 403,
        code: MODEL_CENTER_CODES.catalogScopeMismatch.code, message: MODEL_CENTER_CODES.catalogScopeMismatch.message });
      let providedCatalog: ModelCenterCatalogPayload | undefined;
      let providedStorage: ModelCenterStoragePayload | undefined;
      const notes: ModelCenterProblem[] = [];
      if (captured.catalog !== undefined) {
        try { providedCatalog = modelCenterInjectedCatalog(captured.catalog); }
        catch (reason) { notes.push(problemOf(reason, MODEL_CENTER_CODES.catalogInvalid.message)); }
      }
      if (captured.storage !== undefined) {
        try { providedStorage = modelCenterStorage(captured.storage); }
        catch (reason) { notes.push(problemOf(reason, MODEL_CENTER_CODES.storageInvalid.message)); }
      }
      if (captured.hardware !== undefined) {
        setHardware(client.current ? client.current.decodeHardware(captured.hardware) : { state: 'UNKNOWN', reason: MODEL_CENTER_CODES.hardwareUnavailable.code });
      }
      if (providedCatalog && providedStorage) {
        if (request === epoch.current && admit()) {
          setCatalog(providedCatalog); setStorage(providedStorage);
          setSources({ catalog: { state: providedCatalog.models.length ? 'READY' : 'EMPTY' }, storage: { state: 'READY' } });
          setState(providedCatalog.models.length ? 'READY' : 'EMPTY');
          if (notes.length) setProblem(notes[0]);
        }
        return;
      }
      if (!client.current) {
        if (request === epoch.current && admit()) {
          setProblem({ code: MODEL_CENTER_CODES.readFailed.code, message: MODEL_CENTER_CODES.readFailed.message });
          setState('FAILED'); captured.onUnavailable?.();
        }
        return;
      }
      const result = await captured.read(() => client.current!.read(controller.signal));
      if (request !== epoch.current || !admit() || controller.signal.aborted) return;
      const nextCatalog = providedCatalog ?? result.catalog;
      const nextStorage = providedStorage ?? result.storage;
      if (nextCatalog) setCatalog(nextCatalog);
      if (nextStorage) setStorage(nextStorage);
      setCredentials(result.credentials);
      setSources({
        catalog: providedCatalog ? { state: providedCatalog.models.length ? 'READY' : 'EMPTY' } : result.status.catalog,
        storage: providedStorage ? { state: 'READY' } : result.status.storage,
      });
      const denied = [result.status.catalog, result.status.storage].some(item => item.state === 'DENIED');
      if (denied && !nextCatalog && !nextStorage) {
        revoked.current = true;
        setProblem({ code: MODEL_CENTER_CODES.readDenied.code, message: MODEL_CENTER_CODES.readDenied.message });
        setSources({ catalog: { state: 'DENIED', code: MODEL_CENTER_CODES.readDenied.code }, storage: { state: 'DENIED', code: MODEL_CENTER_CODES.readDenied.code } });
        setState('DENIED'); captured.onUnavailable?.();
        return;
      }
      const failed = [result.status.catalog, result.status.storage].some(item => item.state === 'FAILED');
      if (failed && !nextCatalog && !nextStorage) {
        setProblem(notes[0] ?? { code: MODEL_CENTER_CODES.readFailed.code, message: MODEL_CENTER_CODES.readFailed.message });
        setState('FAILED');
        return;
      }
      if (notes.length) setProblem(notes[0]);
      // A successful storage read cannot prove that the model registry is empty.
      // Preserve each source's outcome, including an incomplete runtime observation.
      const catalogStatus = providedCatalog
        ? { state: providedCatalog.models.length ? 'READY' : 'EMPTY' }
        : result.status.catalog;
      const storageStatus = providedStorage ? { state: 'READY' } : result.status.storage;
      const complete = [catalogStatus, storageStatus].every(item => item.state === 'READY' || item.state === 'EMPTY');
      if (!complete) {
        setState(nextCatalog || nextStorage ? 'PARTIAL' : 'FAILED');
        return;
      }
      setState(catalogStatus.state === 'EMPTY' ? 'EMPTY' : 'READY');
    } catch (reason) {
      if (request !== epoch.current || !admit() || controller.signal.aborted) return;
      const problem = problemOf(reason, MODEL_CENTER_CODES.readFailed.message);
      setProblem(problem);
      // 身份/范围不一致是**契约**问题，不是会话被撤销：两者都拒绝读取，但只有真正的
      // 401/403 才进入 DENIED（DENIED 表示"没有权限"，不是"这里没有模型"）。
      const scopeMismatch = reason instanceof ApiError && reason.problem.code.endsWith('_SCOPE_MISMATCH');
      if (reason instanceof ApiError && !scopeMismatch && [401, 403].includes(reason.status)) {
        revoked.current = true; setCatalog(undefined); setStorage(undefined);
        setSources({ catalog: { state: 'DENIED', code: problem.code }, storage: { state: 'DENIED', code: problem.code } });
        setState('DENIED'); captured.onUnavailable?.();
        return;
      }
      // 两个来源都没有成功读取：各自标明失败原因，绝不伪装成"空注册表"或"没有资产"。
      setSources({ catalog: { state: 'FAILED', code: problem.code }, storage: { state: 'FAILED', code: problem.code } });
      setState('FAILED');
    } finally { if (request === epoch.current) pending.current = false; }
  }, [admit]);

  useEffect(() => {
    if (props.active && !props.denied) void reload();
    // 只在视图激活/身份变化时读取一次；没有任何轮询计时器。
  }, [props.active, props.identity, props.denied, reload]);

  return {
    state, problem, catalog, storage, credentials, hardware, sources, selected,
    /** 任何写操作都不可用：原 owner 没有下载/清理端点。 */
    canRead: !props.denied && !revoked.current && props.active && !props.busy && state !== 'LOADING',
    modelCenterWritesAvailable: false as const,
    select: (modelId: string) => setSelected(modelId),
    reload,
  };
}
export type ModelCenterController = ReturnType<typeof useModelCenter>;

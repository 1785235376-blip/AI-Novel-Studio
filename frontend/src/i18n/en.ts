/** [HERMIA-FE-20261025 I18N P0] English dictionary — must satisfy every zh-CN key (compile-time). */
import type { MessageKey } from './zh-CN';
export const en: Record<MessageKey, string> = {
  'lang.group': 'Interface language',
  'lang.zh': '中',
  'lang.en': 'EN',
  'lang.zh.title': 'Switch to Chinese (中文)',
  'lang.en.title': 'Switch to English',
  'theme.group': 'Background',
  'theme.light': 'Light',
  'theme.dark': 'Dark',
  'theme.light.title': 'Light background',
  'theme.dark.title': 'Dark background',
  'mode.group': 'Interface mode',
  'mode.basic': 'Basic',
  'mode.pro': 'Pro',
  'module.tablist': 'Creative modules',
  'module.NOVEL': 'Novel',
  'module.IMAGE': 'Image',
  'module.VIDEO': 'Video',
  'module.AUDIO': 'Audio',
  'module.EDIT': 'Edit',
  'module.ASSETS': 'Assets',
  'module.CONTROL': 'Control',
  'module.PLUGIN': 'Plugins',
  'module.WORKFLOW': 'Workflows',
  'overflow.more': 'More',
  'overflow.proMore': 'Pro more',
  'overflow.aria': 'More workspaces',
  'overflow.aria.pro': 'Pro more workspaces', // [HERMIA-FE-20261025 DUI×I18N] 可访问名须包含可见文本「Pro more」
  'overflow.aria.current': '{prefix}More workspaces (current: {label})',
  'overflow.proPrefix': 'Pro · ',
  'overflow.menu': 'Overflow workspaces',
  'overflow.hint': 'Reachable via Settings, commands or “More” · status comes from the real ledger',
  /* [HERMIA-FE-20261025 DUI×I18N] DUI P0/P1 新增文案 */
  'settings.ariaBasic': 'Open settings',
  'cmd.settingsBasic': 'Open settings',
  'cmd.hint.settingsBasic': 'Settings',
  'cmd.hint.mode': 'Interface mode',
  'cmd.hint.sidebar': 'Sidebar',
  'orient.dismissAll': "Don't show again",
  'rail.unavailable': 'Unavailable',
  'scope.unnamedWorkspace': 'Selected workspace (untitled)',
  'scope.unnamedProject': 'Selected work (untitled)',
  'scope.unnamedStoryline': 'Selected storyline (untitled)',
  'scope.unnamedBranch': 'Selected branch (untitled)',
  'chapter.unreadable': 'Chapters unavailable right now',
  'chapter.notOpen': 'No chapter open',
  'lt.simpleTitle': 'Ask assistant',
  'lt.simpleIntro': 'Use the assistant on your computer to see what to do next; you confirm before anything is sent.',
  'lt.simpleClose': 'Close assistant',
  'lt.close': 'Close',
  'lt.disconnected': 'Assistant not connected',
  'lt.disconnectedBody': 'No assistant found on your computer. Writing is unaffected; to use it, open the assistant on your computer, then click “Retry”.',
  'lt.retry': 'Retry',
  'lt.connected': 'Assistant connected',
  'lt.confirmingStop': 'Confirming sharing has stopped',
  'lt.cancel': 'Cancel current request',
  'lt.closeDisconnect': 'Close and disconnect',
  'lt.techDetails': 'How to connect · technical details',
  // [HERMIA-FE-20261025 VERA-FIX] Vera re-review keys
  'ct.retryLater': 'Please try again later.',
  'save.viewConflict': 'View conflict',
  'save.exportDraft': 'Export current draft',
  'as.currentlyWriting': 'Writing now',
  'settings.label': 'Settings',
  'settings.aria': 'Open settings (AI control and plugins)',
  'settings.menu': 'Settings and overflow workspaces',
  'settings.hint': 'AI control and plugins open from Settings or “More” · status comes from the real ledger',
  'settings.control': 'AI control',
  'settings.plugin': 'Plugin manager',
  'search.aria': 'Open global commands',
  'search.placeholder': 'Search chapters, commands', // [HERMIA-FE-20261025 VERA-FIX MF-2] shorter so it fits beside Ctrl K at 1440
  'header.capability': 'Capabilities',
  'header.tasks': 'Tasks',
  'context.writingAria': 'Current writing scope',
  'context.scopeAria': 'Current creative scope',
  'context.untitledWork': 'Untitled work',
  'actor.local': 'Local author',
  'shell.sidebarAria': 'Structure and navigation',
  "tour.count": "Step {n} of {total}",
  "tour.skip": "Skip",
  "tour.prev": "Back",
  "tour.next": "Next",
  "tour.done": "Done",
  "tour.sessionOnly": "Not signed in: \"tour seen\" is remembered for this session only and may show again later.",
  "tour.modules.title": "Six creative modules",
  "tour.modules.body": "Novel, Image, Video, Audio, Edit and Assets live in this row. Click to switch; your work stays put.",
  "tour.work.title": "The workspace",
  "tour.work.body": "Write, place images and arrange shots here. For a novel, you type the text right here.",
  "tour.assist.title": "Creative assist",
  "tour.assist.body": "On the right (or the button on the right edge): next-step tips, characters and AI help. AI text is a candidate until you click Adopt.",
  "tour.settings.title": "Look, language and settings",
  "tour.settings.body": "Top right switches light / dark and Chinese / English. Settings holds AI settings and \"Replay tour\".",
  "tour.save.title": "Save status",
  "tour.save.body": "The bottom bar shows where your work is saved, whether it is saved, and AI task progress.",
  "tour.pro.title": "Pro mode",
  "tour.pro.body": "You are in Pro mode: extra tools like capability status and diagnostics. On the Video page you can open the dual canvas. You can switch back anytime.",
  "settings.replayTour": "Replay tour",
  'context.unselected': 'Not selected',
  'context.untitledNovel': 'Untitled novel',
  'context.unnamedAria': 'Untitled novel · click to complete the overview',
  'context.openOverview': 'Open overview of “{book}”',
  'context.completeOverview': 'Click to complete the overview',
  'context.review': 'Tasks / candidates / review',
  'context.workspace': 'Workspace: ',
  'context.projectLabel': '{noun}: ',
  'context.storyline': 'Storyline: ',
  'context.branch': 'Branch: ',
  'noun.novel': 'Novel',
  'noun.project': 'Project',
  'inspector.title': 'Writing assistant',
  'inspector.collapse': 'Collapse sidebar',
  'inspector.expand': 'Expand sidebar',
  'inspector.resize': 'Resize inspector panel',
  'status.taskSummaryAria': 'Cross-module task summary',
  'status.taskSummary': 'Tasks {running} running / {failed} failed / {cancelled} cancelled / {queued} queued',
  'tasks.viewFailed': 'View failed tasks',
  'tasks.failedTitle': 'Failed tasks',
  'tasks.closeFailed': 'Close failed tasks',
  'tasks.locate': 'Click to open the related workspace',
  'tasks.publishedOnly': 'Only published real task summaries are shown.',
  'tasks.failedCount': '{count} failed',
  'tasks.noneFailed': 'No failed tasks',
  'cmd.dialog': 'Global commands',
  'cmd.placeholder': 'Search modules or commands',
  'cmd.list': 'Available commands',
  'cmd.empty': 'No matching commands',
  'cmd.inspector': 'Open inspector panel',
  'cmd.modeBasic': 'Switch to Basic mode',
  'cmd.modePro': 'Switch to Pro mode',
  'cmd.settingsHub': 'Open settings (AI control)',
  'cmd.providers': 'Open provider control center',
  'cmd.plugins': 'Open plugin manager',
  'cmd.workflow': 'Open workflow workspace',
  'cmd.hint.settings': 'Settings · AI control', // [HERMIA-FE-20261025 VERA-FIX MF-4] no internal id
  'cmd.hint.providers': 'AI control', // [HERMIA-FE-20261025 VERA-FIX MF-4]
  'cmd.hint.plugins': 'Plugins', // [HERMIA-FE-20261025 VERA-FIX MF-4]
  'cmd.hint.workflow': 'Workflows', // [HERMIA-FE-20261025 VERA-FIX MF-4]
  'cmds.trigger': 'Search features',
  'cmds.dialog': 'Search features and commands',
  'cmds.placeholder': 'Type a feature name, e.g. version history / control / pro',
  'cmds.list': 'Matching features',
  'cmds.group.写作': 'Writing',
  'cmds.group.媒体': 'Media',
  'cmds.group.布局': 'Layout',
  'cmds.group.壳·设置': 'Shell & settings',
  'cmds.noMatch': 'No feature matches “{q}”. Try a shorter keyword or a feature ID (e.g. history, plugin).',
  'cmds.noCommands': 'No commands are available right now.',
  'cmds.blocked': 'Cannot run: {reason}',
  'cmds.stale': 'The project or chapter changed. Please select again.',
  'cmds.duplicate': 'Opening, please wait.',
  'cmds.needsConfirm': 'This needs confirmation before it can run.',
  'cmds.failed': 'Failed to run. Please try again.',
  'common.close': 'Close',
  'common.cancel': 'Cancel',
  'common.confirm': 'Confirm',
  'common.retry': 'Retry',
  'common.save': 'Save',
  'common.loading': 'Loading…',
  'common.empty': 'Nothing here yet',
  'common.error': 'Something went wrong. Please try again later.',
  'common.chars': '{count, plural, one {# character} other {# characters}}',

  // [HERMIA-FE-20261025 I18N P1/P2]
  'orient.region': 'Current creation guide',
  'orient.chip': 'First time here',
  'orient.what': 'What you are creating',
  'orient.can': 'What you can do now',
  'orient.effect': 'What your actions affect',
  'orient.dismissAria': 'Hide guide',
  'orient.dismiss': 'Hide',
  'orient.tabs': 'Workspace views',
  'orient.noWork': 'No work open yet',
  'orient.novelCan': 'Edit chapters at the desk · AI output becomes a candidate and enters the text only after you adopt it · settings enter canon only after review',
  'orient.effectCloud': 'Auto-saves to the collaboration service; adopting a candidate never overwrites approved settings',
  'orient.effectLocal': 'Auto-saves on this device; adopting a candidate never overwrites approved settings',
  'status.save': 'Save: {v}',
  'status.conn': 'Connection: {v}',
  'status.connCloud': 'collaboration service',
  'status.connLocal': 'this device',
  'status.ai': 'AI tasks: {v}',
  'status.aiRunning': 'generating',
  'status.aiFailed': 'failed',
  'status.aiDone': 'completed',
  'status.aiQueued': 'queued',
  'status.aiNone': 'none running',
  'status.lastPosPending': 'Checking account, then returning to last chapter…',
  'status.lastPosTimeout': 'Account check is slow: pick a chapter manually (position not saved yet)',
  'status.lastPosFailed': 'Account check failed: pick a chapter manually, position not saved; retries when back online',
  'status.lastPosSession': 'Chapter position: this session only',
  'dui.title': 'Tasks & results',
  'dui.close': 'Close',
  'dui.noTarget': 'This task has no recorded work location, so results and history are unavailable here.',
  'dui.resultsNote': 'Results (adopt manually after confirming; never written to settings)',
  'dui.historyNote': 'Work history (restoring appends a new version)',
  'save.locCloud': 'Saved to: collaboration service',
  'save.locLocal': 'Saved to: this device',
  'save.saved': 'Saved',
  'save.dirty': 'Unsaved changes',
  'save.saving': 'Saving…',
  'save.conflict': 'Save conflict — resolve it first',
  'save.failed': 'Save failed — please retry',
  'save.opening': 'Opening chapter…',
  'save.composing': 'Typing…',
  'save.backendSaved': 'Saved on server',
  'save.submitting': 'Submitting, waiting for server confirmation…',
  'save.offlineDurable': 'Offline draft stored in this browser; not yet confirmed by server',
  'save.offlineMem': 'Offline draft only in page memory; not yet stored',
  'save.backendFailed': 'Server did not confirm the save — please retry',
  'save.draftDurable': 'Draft stored locally, pending submit',
  'save.draftMem': 'Draft only in memory; not yet stored',
  'nv.overview': 'Overview',
  'nv.writer': 'Writing desk',
  'nv.outline': 'Outline',
  'nv.cast': 'Characters',
  'nv.canon': 'Canon',
  'nv.continuity': 'Continuity',
  'nv.revision': 'Versions',
  'nv.storyAll': 'Outline · Characters · World',
  'nv.checkAll': 'Continuity · Pending canon',
  'nv.history': 'Versions / Revisions',
  'nv.creation': 'Creation plans',
  'nv.import': 'Import',
  'nv.export': 'Export',
  'nv.research': 'Research',
  'nv.screenplay': 'Screenplay',
  'nv.adaptation': 'Adaptation',
  'nv.workflow': 'Workflow',
  'nv.agents': 'AI tasks',
  'nv.openChapterFirst': 'Open a chapter first',
  'nv.exportHint': 'Export and download work; cancel / retry not wired yet',
  'rail.structure': 'Work structure',
  'rail.chapters': 'Chapters',
  'rail.vol1': 'Volume 1',
  'rail.loading': 'Loading chapters…',
  'rail.error': 'Chapters could not be loaded. Please try again later.',
  'rail.noChapters': 'No chapters yet.',
  'rail.untitled': 'Untitled',
  'rail.new': '+ New chapter',
  'rail.panels': 'Novel panels',
  'rail.more': 'More (chapter management · all features)',
  'rail.st.ok': 'Connected',
  'rail.st.part': 'Partial',
  'rail.st.local': 'Local only',
  'rail.st.off': 'Backend not connected',
  'rail.tree': 'Chapter tree',
  'rail.wordsUnknown': 'Word count unknown',
  'pat.chapter': 'Chapter {n} · {title}',
  'pat.chars': '{n} chars',
  'pat.charsVer': '{n} chars · v{v}',
  'pat.version': 'Version {v}',
  'pat.pov': 'Current POV: {v}',
  'pat.goal': 'Goal {cur} / {target} chars',
  'desk.noChapter': 'No chapter selected',
  'desk.novel': 'Novel',
  'desk.back': 'Back to desk',
  'desk.history': 'Version history',
  'desk.nothingOpen': 'No chapter is open yet',
  'desk.pickHint': 'Create or select a chapter on the left to start writing.',
  'desk.recoverFirst': 'Handle the draft recovery candidate first',
  'desk.goalBad': 'Writing goal data is incomplete; refresh and retry. The text can still be edited and saved.',
  'empty.region': 'No chapters yet',
  'empty.ph': 'Select or create a chapter on the left first',
  'empty.hint': 'This work has no chapters yet. Create one to write here; content saves automatically.',
  'empty.story': 'Plan the story first',
  'empty.storyDesc': 'Characters, world and outline',
  'empty.import': 'Import an existing manuscript',
  'empty.importDesc': 'Import existing text as chapters',
  'as.region': 'Writing sidebar',
  'as.ctx': 'Current writing context',
  'as.current': 'Current chapter',
  'as.next': 'Next step',
  'as.outline': 'Outline / chapter flow',
  'as.noOutline': 'No outline items yet; add them in story planning.',
  'as.cast': 'Characters / appearances',
  'as.noCast': 'No characters linked to this chapter yet.',
  'as.manageCast': 'Manage characters',
  'as.check': 'Continuity check',
  'as.ai': 'AI writing',
  'as.aiModes': 'AI writing modes',
  'as.continue': 'Continue',
  'as.rewrite': 'Rewrite selection',
  'as.polish': 'Polish',
  'as.brainstorm': 'Brainstorm',
  'as.aiHint': 'Pick a mode, then confirm in the full panel to generate; results arrive as candidates.',
  'as.openFull': 'Open full AI panel',
  'as.openFullExtras': 'Open full AI panel (incl. writing goals)',
  'as.drawer': 'AI writing · full panel',
  'as.moreTools': 'More writing tools',
  'as.pickHint': 'Select or create a chapter from the work structure on the left',
  'as.candidate': 'A candidate awaits your review',
  'cta.adopt': 'Adopt draft',
  'cta.continuity': 'Check continuity',
  'cta.continue': 'Keep writing',
  'cta.pick': 'Select or create a chapter on the left',
  'cta.draft': 'Generate draft',
  'cta.story': 'Story planning',
  'cta.pending': 'Pending canon',
  'tk.noWork': 'Open a work first.',
  'tk.audiobook': 'Audiobook',
  'tk.motion': 'Motion',
  'tk.ws': 'Workspace',
  'tk.export': 'Export',
  'tk.chapterN': 'Chapter {id}',
  'tk.media': 'Media tasks',
  'tk.asset': 'Asset tasks',
  'tk.wsTasks': 'Workspace tasks',
  'tk.view': 'Task views',
  'tk.tasks': 'Tasks',
  'tk.trash': 'Trash',
  'tk.stats': 'Asset task stats',
  'tk.total': 'Total {n}',
  'tk.running': 'Running {n}',
  'tk.pending': 'Queued {n}',
  'tk.failed': 'Failed {n}',
  'tk.list': 'Task list',
  'tk.loading': 'Loading…',
  'tk.none': 'No running or recent tasks.',
  'tk.errOf': '{name}: {err}',
  'tk.trashErr': 'Failed to load trash: {err}',
  'tk.trashEmpty': 'Trash is empty.',
  'tk.s.queued': 'Queued',
  'tk.s.running': 'Running',
  'tk.s.done': 'Done',
  'tk.s.failed': 'Failed',
  'tk.s.cancelled': 'Cancelled',
  'spg.region': 'Settings path',
  'spg.title': 'Settings · how to find them',
  'spg.desc': 'AI control and plugins are not among the default 6 buttons. Open their full workspaces from the header “Settings”, “More”, or a command.',
  'spg.actions': 'Open overflow workspaces',
  'spg.control': 'Open AI control',
  'spg.plugin': 'Open plugins',
  'spg.workflow': 'Open workflows',
  'spg.note': 'No fake green · connectivity reflects the real ledger',
  'pr.busy': 'Processing',
  'pr.close': 'Close',
  'pr.closeOf': 'Close {title}',
  'he.noProject': 'Open a novel project first',
  'he.openProject': 'Open project',
  'he.noChapter': 'No chapter selected yet',
  'he.noChapterDetail': 'The main writing path needs a current chapter. Pick one from the chapter tree on the left, or create one to continue.',
  'he.pickChapter': 'Pick a chapter',
  'he.loadFail': 'Failed to load',
  'he.retry': 'Retry',
  'he.loading': 'Loading…',
  'he.noSel': 'Nothing selected yet',
  'he.d.NOVEL': 'The writing workspace needs an open book. Open or create a project to continue.',
  'he.sel.NOVEL': 'Select a chapter or outline item and the right sidebar will suggest the next step.',
  'he.failDetail': '{ws} content could not be read. You can retry; nothing retries automatically or pretends to be connected.',
  'he.loadingDetail': 'Reading the real state of {ws}, please wait.',
  'ws.NOVEL': 'Novel',
  'ws.IMAGE': 'Image',
  'ws.VIDEO': 'Video',
  'ws.AUDIO': 'Audio',
  'ws.EDIT': 'Edit',
  'ws.ASSETS': 'Assets',
  'fmt.bytes': '{n} bytes',
  'fmt.unknown': 'Unknown',
  'fmt.unknownTime': 'unknown time',

  'context.sep': ': ',
  'pat.orientWhat': '“{book}” · Chapter {n} · {title}',

  'he.d.IMAGE': 'Image previews, references and generation tasks are scoped per project. Open a project to enter the image workspace.',
  'he.d.VIDEO': 'The three video layers (shot script / canvas / director) need to be bound to a project.',
  'he.d.AUDIO': 'Voice-over, sound effects and audiobook lists need to be bound to a project.',
  'he.d.EDIT': 'The multi-track edit timeline needs to be bound to a project. The NLE is not embedded in the novel area.',
  'he.d.ASSETS': 'Files and references in the asset library are scoped per project. Open a project to browse.',
  'he.noClips': 'No clips on the timeline yet',
  'he.noClipsDetail': 'This sequence has no track clips yet. Reference media from the pool, or send clips from Video, then edit.',
  'he.openPool': 'Open media pool',
  'he.noAssets': 'No assets in the library yet',
  'he.noAssetsDetail': 'This project\'s asset library is empty (0 items). Import files, or generate in Image / Audio / Video and come back to reference them. This is not an image generator.',
  'he.refSemantics': 'Learn about references',
  'he.sel.IMAGE': 'No image task selected. Start a generation, add references, or open the comic entry.',
  'he.sel.VIDEO': 'No shot selected. Pick a node on the canvas, open the director desk, or send to Edit.',
  'he.sel.AUDIO': 'No audio task selected. Create voice-over / SFX / audiobook; send finished pieces to Edit.',
  'he.sel.EDIT': 'Select a clip on the timeline to see in/out points. With nothing selected, sequence output and export stay available.',
  'he.sel.ASSETS': 'No asset selected. Filter or import; dragging to another module references it without copying.',
  'he.mark': 'Honest empty state · no fake green',

  'ct.title': 'Story structure',
  'ct.new': 'New chapter',
  'ct.reordering': 'Saving chapter order…',
  'ct.loading': 'Loading chapters',
  'ct.loadErr': 'Couldn\'t load chapters: {err}',
  'ct.emptyTitle': 'No chapters yet',
  'ct.emptyDetail': 'There are no chapters in the manuscript yet. Create one to start writing, or restore a removed chapter.',
  'ct.list': 'Chapter list',
  'ct.chTitle': 'Chapter title',
  'ct.save': 'Save',
  'ct.cancel': 'Cancel',
  'ct.create': 'Create chapter',
  'ct.drag': 'Drag to reorder chapters',
  'ct.rename': 'Rename {title}',
  'ct.more': 'More actions for {title}',
  'ct.archived': 'Removed chapters',
  'ct.noArchived': 'No removed chapters.',
  'ct.restore': 'Restore to manuscript',
  'ct.delete': 'Permanently delete {title}',
  // [HERMIA-FE-20261025 VERA-FIX] name must contain visible text "Features" (axe label-content-name-mismatch)
  'fl.open': 'Open Features navigator',
  'fl.close': 'Close Features navigator',
  'fl.label': 'Features',
  'lt.ask': 'Ask assistant',
  // [HERMIA-FE-20261025 VERA-097 P3] rebuildApi/useModelCenter/AssetsRebuild 英文漏翻
  'mc.err.catalogInvalid': 'Model catalog data is unavailable or not in the shape the service declared. Please reload.',
  'mc.err.runtimeInvalid': 'Runtime status data is unavailable or not in the shape the service declared. Please reload.',
  'mc.err.catalogScopeMismatch': 'The model catalog does not match the current project or branch. Please reopen.',
  'mc.err.storageInvalid': 'Storage data is unavailable or not in the shape the service declared. Please reload.',
  'mc.err.storageScopeMismatch': 'Storage data does not match the current project or branch. Please reopen.',
  'mc.err.credentialInvalid': 'Credential status is unavailable, or the service returned fields it should not expose. Please reload.',
  'mc.err.hardwareInvalid': 'Host hardware facts are unavailable or not in the declared shape.',
  'mc.err.catalogUnavailable': 'This service does not provide model catalog reads; shown as "unknown".',
  'mc.err.runtimeUnavailable': 'This service does not provide runtime status reads; shown as "unknown".',
  'mc.err.credentialUnavailable': 'This service does not provide credential status reads; only "unknown" is shown.',
  'mc.err.hardwareUnavailable': 'This service does not provide host hardware facts; VRAM and memory are not guessed.',
  'mc.err.readDenied': 'This session may not read the model center. Please re-check identity and branch.',
  'mc.err.readFailed': 'Model center read failed. Please check again later.',
  'mc.err.cleanupUnavailable': 'The owner declares physical_cleanup_available=false: this view offers no cleanup or migration.',
  'mc.err.downloadUnavailable': 'The owner has no download endpoint: this view offers no download, preparation or repair.',
  'mc.err.routeBlocked': 'No executable model route right now; every fact blocking this model is listed below.',
  'mc.err.routeUnknown': 'Owner facts needed to decide selectability are missing; treated as "unknown", not selectable.',
  'mc.err.secretValueRejected': 'The service returned credential fields it should not expose; the response was rejected.',
  'mc.err.orphanUnverifiable': 'The owner read-only projection has no per-item deletion records, so no orphan candidates can be produced.',
  'rb.err.disabled': 'This feature is not enabled on the backend (experimental flag off)',
  'rb.err.404': 'The backend has no such endpoint (404)',
  'rb.err.session': 'A signed-in session is required',
  'rb.err.forbidden': 'Permission denied',
  'rb.err.status': 'The backend returned an error ({status})',
  'rb.err.unreachable': 'Backend unavailable (cannot connect)',
  'rb.ast.loadFailed': 'The asset library cannot be read right now. Please try again later.',
  'rb.ast.refsShortFailed': 'Not available right now',
  'rb.ast.refsFailed': 'References are not available right now.',
  'rb.ast.imported': 'Imported “{name}”',
  'rb.ast.importFailed': 'Import failed: {msg}',
  'rb.ast.deleted': 'Moved to trash: {name}',
  'rb.ast.deleteFailed': 'Delete failed: {msg}',
  'rb.ast.restored': 'Restored: {name}',
  'rb.ast.restoreFailed': 'Restore failed: {msg}',
  // [HERMIA-FE-20261025 P1-ERR] apiErrorView 友好错误文案（白名单）
  'err.http.400': 'The request was invalid. Please check and try again.',
  'err.http.401': 'Your session has expired. Please sign in again.',
  'err.http.403': 'You do not have permission to do this.',
  'err.http.404': 'The requested item does not exist or was deleted.',
  'err.http.408': 'The request timed out. Please try again shortly.',
  'err.http.409': 'This item was changed elsewhere. Refresh and try again.',
  'err.http.413': 'The content is too large to submit.',
  'err.http.422': 'The submitted content did not pass validation. Please check and try again.',
  'err.http.429': 'Too many requests. Please wait a moment and try again.',
  // [HERMIA-FE-20261025 VERA-F70 MF-2] str(exc) 类业务 code 的友好文案
  'err.code.INVALID_PROVIDER_CONFIG': 'The model provider configuration is invalid. Check the settings and try again.',
  'err.code.ASSET_INTEGRITY_FAILED': 'The asset file failed its integrity check. Please import it again.',
  'err.code.IMAGE_EDIT_INVALID': 'The image edit settings are invalid. Adjust them and try again.',
  'err.code.INVALID_WORKER_CONFIG': 'The background worker configuration is invalid. Please check the settings.',
  'err.code.EXPERIMENTAL_INVALID': 'The experimental feature request is invalid. Please check and try again.',
  // [HERMIA-FE-20261025 VERA-fbe029c4 §2] error meta labels
  'err.label.code': 'Code: ',
  'err.label.requestId': 'Request ID: ',
  'err.label.details': 'Details: ',
  'err.code.TEXT_PROVIDER_NOT_CONFIGURED': 'No text model is configured yet. Add and enable a text model in Settings first.',
  // [HERMIA-FE-20261025 VERA-e471dc76 P3-1] 白名单内英文后端字面文案的本地化（仅当 message 与后端字面完全一致时替换）
  'err.srv.CANON_RECOVERY_REQUIRED': 'Commit interrupted; refresh and recover the existing receipt.',
  'err.srv.EXPORT_CANCELLED': 'export cancelled',
  'err.srv.EXPORT_NOT_CANCELLABLE': 'export is no longer cancellable',
  'err.srv.EXPORT_NOT_READY': 'export is not ready',
  'err.srv.EXPORT_NOT_RETRYABLE': 'export is not retryable',
  'err.srv.EXPORT_RESULT_INVALID': 'export result is unavailable',
  'err.srv.FORK_STALE_OR_CONFLICT': 'Refresh the authorized comparison or inspect recovery; no automatic retry.',
  'err.srv.INVALID_EXPECTED_VERSION': 'expected_version must be a non-negative integer',
  'err.srv.INVALID_VIDEO_PROVIDER_CONFIG': 'invalid video provider id',
  'err.srv.NODE_EXECUTION_FAILED': 'The node did not complete; explicitly retry after review.',
  'err.srv.PLUGIN_HOST_ADMIN_REQUIRED': 'Package mutations require a local host management session.',
  'err.srv.PORTABLE_CHAPTER_VERSION_CONFLICT': 'The original chapter changed; review the preserved recovery record.',
  'err.srv.PRECONDITION_REQUIRED': 'Read the current screenplay edit_version and include expected_version before editing or approving.',
  'err.srv.REALTIME_VERSION_OR_SOURCE_CONFLICT': 'Refresh the scoped document and inspect preserved operations.',
  'err.srv.SYNC_STALE_OR_CONFLICT': 'Refresh and review current candidates; uncertain writes must be reconciled.',
  'err.srv.WORKFLOW_EXECUTION_PROVENANCE_REQUIRED': 'This saved run has no verified project identity. Create a new workflow run and review its agent step.',
  'err.srv.WORKFLOW_PROJECT_CHANGED': 'The original project identity is no longer current. Create a new workflow run for the current project.',
  'err.http.500': 'Something went wrong on the server. Please try again shortly.',
  'err.http.502': 'The service is unreachable right now. Please try again shortly.',
  'err.http.503': 'The service is unreachable right now. Please try again shortly.',
  'err.http.504': 'The service took too long to respond. Please try again shortly.',
  'err.technical': 'Technical details',
  // [HERMIA-FE-20261025 MERGE-FEC i18n] fe-contracts strings
  'fc.prod.moreFailed': 'Could not load the next page; tasks already shown are unchanged. You can click “Load more production tasks” again — nothing retries automatically.',
  'fc.prod.ownerLabel': 'Task type',
  'fc.prod.ownerAll': 'All (image and video)',
  'fc.prod.ownerImage': 'Image',
  'fc.prod.ownerVideo': 'Video',
  'fc.prod.opLabel': 'Operation',
  'fc.prod.opAll': 'All operations',
  'fc.prod.loaded': 'Loaded {loaded} · {total} matched in this read (matches for this read only, not the total number of tasks)',
  'fc.prod.loadMore': 'Load more production tasks',
  'fc.prod.noNext': 'No next page in this read; tasks added or removed while paging can change results — reload when needed.',
  'fc.prod.noPaging': 'The service returned no paging info; results are shown as before.',
  'fc.prod.queryInvalid': 'Invalid production task filter.',
  'fc.tc.loaded': 'Loaded {loaded} · {total} matches observed in this read (not the total number of tasks)',
  'fc.tc.loadMore': 'Load more tasks',
  'fc.tc.noNext': 'No next page in this read (this does not mean every past task is listed; look for older or out-of-range records in the original task tool).',
  'fc.tc.moreFailed': 'Could not load the next page; tasks already shown are unchanged. You can click “Load more tasks” again — nothing retries automatically.',
  'fc.tc.summaryLoaded': 'Loaded',
  'fc.tc.summaryTotal': 'Total',
  'fc.tc.summaryMeta': '{prefix} {total} · progress unknown {noProgress} · source changed {stale} · unreadable sources {unavailable}',
  'fc.tc.summaryTruncated': ' · display limit reached',
  'fc.aud.assetRestore': 'Undo delete',
  'fc.aud.assetRestoreHint': '“Undo delete” only puts the asset back from the trash; it does not roll back to an older version.',
  'fc.aud.timelineOnly': 'Only the timeline has version history; view and restore a version there.',
  'fc.aud.assetHistory': 'Version history for a single asset is not supported yet.',
  'fc.aud.restoring': 'Restoring…',
  'fc.aud.restoreNote': 'After restore the asset returns to its original place and references work again.',

  // [HERMIA-FE-20261025 I18N-ROUGH]
  'rough.0': 'Reference images, character looks and keyframes for this work',
  'rough.1': 'Describe a shot to generate candidates, or add references to keep consistency',
  'rough.2': 'Generation uses the image model set up in AI Control; you confirm before dispatch',
  'rough.3': 'Shots, visual relations and director suggestions for this chapter',
  'rough.4': 'Break down shots, link references on the canvas, adopt director suggestions',
  'rough.5': 'No final cut here; "Send to Edit" when ready',
  'rough.6': 'Voice-over, sound effects and audiobook for this work',
  'rough.7': 'Preview, synthesize voice, generate effects, track the audiobook',
  'rough.8': 'No multitrack editing here; "Send to Edit" when ready',
  'rough.9': 'The final cut of this work',
  'rough.10': 'Place shots and sound on the multitrack timeline, cut, set in/out points',
  'rough.11': 'Arrangement stays on this page and is not saved; export is not connected yet',
  'rough.12': 'Images, video, sound and documents of this work',
  'rough.13': 'Import, filter, see source and usage, send to other modules',
  'rough.14': 'Sends references, never copies files',
  'rough.15': 'Image workspace',
  'rough.16': 'Video workspace',
  'rough.17': 'Sound workspace',
  'rough.18': 'Edit workspace',
  'rough.19': 'Assets workspace',
  'rough.20': 'Asset library',
  'rough.22': 'Image studio',
  'rough.23': 'Video studio',
  'rough.24': 'Multitrack timeline',
  'rough.25': 'Media pool',
  'rough.26': 'Export final cut',
  'rough.27': 'Browse',
  'rough.28': 'Image canvas',
  'rough.29': 'Generate',
  'rough.30': 'Comic',
  'rough.31': 'Shot script',
  'rough.32': 'Storyboard',
  'rough.33': 'Sound library',
  'rough.34': 'Voice / SFX / Audiobook',
  'rough.36': 'New generation',
  'rough.37': 'Import from assets',
  'rough.38': 'Add reference',
  'rough.39': 'Open comic',
  'rough.40': 'Generate candidates…',
  'rough.41': 'Open AI Control',
  'rough.42': 'Send to Edit',
  'rough.43': 'Send to Edit (hand-off)',
  'rough.44': 'Break down from script',
  'rough.45': '+ Shot',
  'rough.46': 'New voice-over',
  'rough.47': 'Send to Edit…',
  'rough.48': 'Write a line',
  'rough.49': 'New sound effect',
  'rough.50': 'Open audiobook list',
  'rough.51': 'Export final cut…',
  'rough.52': 'Back to Video',
  'rough.53': 'Bring from Video',
  'rough.54': '▶ Play',
  'rough.55': 'Import…',
  'rough.56': 'All assets',
  'rough.57': 'Narrow nav',
  'rough.58': 'Switch view or item',
  'rough.59': 'Asset type',
  'rough.60': 'Pick a shot',
  'rough.61': 'Images',
  'rough.62': 'Audio',
  'rough.63': 'Docs / other',
  'rough.64': 'No shots yet',
  'rough.65': 'Current view',
  'rough.66': 'Make a video in three steps', // [HERMIA-FE-20261030 VERA-P3]
  'rough.67': '① List the shots', // [HERMIA-FE-20261030 VERA-P3]
  'rough.68': '② Arrange references on the canvas', // [HERMIA-FE-20261030 VERA-P3]
  'rough.69': '③ Read the director notes', // [HERMIA-FE-20261030 VERA-P3]
  'rough.70': 'Select an image first to overlay references', // [HERMIA-FE-20261030 VERA-P3]
  'rough.71': 'Image generation', // [HERMIA-FE-20261030 VERA-P3]
  'rough.72': 'Reference overlay: on', // [HERMIA-FE-20261030 VERA-P3]
  'rough.73': 'Reference overlay: off', // [HERMIA-FE-20261030 VERA-P3]
  'rough.74': 'Plan shots and how frames relate here; cut the final video on the Edit page.', // [HERMIA-FE-20261031 VERA-P3-3]
  'rough.75': 'Cards · references · links', // [HERMIA-FE-20261031 VERA-P3-3]
  'rough.76': 'Nodes · asset refs · relation edges', // [HERMIA-FE-20261031 VERA-P3-3]
  'rough.77': 'Three-layer workspace', // [HERMIA-FE-20261031 VERA-P3-3]
  'rough.78': '① Shot script', // [HERMIA-FE-20261031 VERA-P3-3]
  'rough.79': '② Infinite canvas', // [HERMIA-FE-20261031 VERA-P3-3]
  'rough.80': '③ Built-in director desk', // [HERMIA-FE-20261031 VERA-P3-3]
  'rough.81': 'Formal production and server save for the selected node', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.82': 'Open formal generation and server save', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.83': 'Links only this node’s position and formal result. Prompts, links and other nodes stay browser drafts; every step needs its own confirmation.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.84': 'The project overview shows independent Studio is not enabled for this project yet; enable it before formal generation.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.85': 'Enable independent Studio…', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.86': 'Enable independent Studio for this project?', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.87': 'Confirm and enable', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.88': 'Saves one “independent Studio entry” record on the server so formal image, video and audio production can be used. It does not change the manuscript, chapters, permissions or project type, and it does not generate, run or adopt anything.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.89': 'After enabling, images keep using formal nodes on this Image page; the Video, Audio, Edit and Assets pages switch to the Studio layout. There is currently no undo control in the UI.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.90': 'Independent Studio enabled. The formal task for this node is below; each step still needs its own confirmation.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.91': 'Missing a verifiable project incarnation or author identity; cannot set up the server node target.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.92': 'Enabling failed: ', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.93': 'Please try again later.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.94': 'The formal workspace is unavailable right now.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.95': 'Formal image node and saved position', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.96': 'Formal image node task', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.97': 'Close formal node task', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.98': 'Node', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.99': 'position', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.100': '. Creates the production job for this node only; prompts, links and other nodes stay browser drafts.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.101': 'First save a blank work position explicitly, then preview, queue, run and review by hand, one step at a time. After approval, adoption needs its own confirmation; incompatible legacy queue results never become a formal source.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.102': 'Save a formal blank position for this node', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.103': 'Recheck this blank-position creation', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.104': 'Original queue request awaiting check: ', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.105': 'Check the original image job queue result', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.106': 'Read this node’s saved position and jobs', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.107': 'Original position request ID: ', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.108': 'The original identity, permission or node changed. Deselect, select the node again and reopen the entry; earlier confirmations are not restored.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.109': 'The result still needs checking. This instance is read-only and will not resend; the original input and request ID are kept.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.110': 'View saved node position', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.111': 'Open the original formal node task', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.112': 'Adopt into the original node position', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.113': 'The production owner has recorded the manual review. This rechecks source metadata only and does not replace candidate preview or review; saving pins the result back to the original node position.', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.114': 'Check the formal result and the original node position', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.115': 'I confirm adopting this formal asset into the original node position', // [HERMIA-FE-20261031 VERA-P3c]
  'rough.116': 'Confirm adoption and save node position', // [HERMIA-FE-20261031 VERA-P3c]
  // [HERMIA-FE-20261030 NSFW]
  'nsfw.menu.label': 'Adult content (NSFW) mode',
  'nsfw.menu.on': 'On',
  'nsfw.menu.off': 'Off',
  'nsfw.menu.turnOn': 'Turn on…',
  'nsfw.menu.turnOff': 'Turn off',
  'nsfw.honest': 'Interface preference only, backend not connected: generation, models and export are unchanged.',
  'nsfw.saved': 'Saved in this browser for the current account and project.',
  'nsfw.session': 'This session only: no signed-in identity or project scope; resets to off on reload.',
  'nsfw.dialog.title': 'Turn on adult content (NSFW) mode?',
  'nsfw.dialog.age': 'For adults aged 18 or older only.',
  'nsfw.dialog.resp': 'You are responsible for what you create and export, and must follow local laws and platform rules.',
  'nsfw.dialog.backend': 'For now this is an interface preference only: the backend content policy is not connected, so no model or generation limit is lifted and export is unchanged.',
  'nsfw.dialog.ack': 'I am 18 or older and understand the above',
  'nsfw.dialog.confirm': 'Turn on',
  'nsfw.dialog.cancel': 'Cancel',
  'nsfw.badge': 'NSFW mode',
  'nsfw.badge.title': 'Adult content (NSFW) mode is on · interface preference only, backend not connected',
  'nsfw.badge.off': 'Turn off NSFW mode',
  'nsfw.badge.offShort': 'Off',
  'nsfw.badge.session': 'this session only',
  // [HERMIA-FE-20261030 B4] EditRebuild 主表面
  'edit.rb.1': 'Media pool · references',
  'edit.rb.2': 'Source monitor',
  'edit.rb.3': 'Program monitor',
  'edit.rb.4': 'Sequence properties',
  'edit.rb.5': 'No clip selected',
  'edit.rb.6': 'Duration',
  'edit.rb.7': 'In / Out',
  'edit.rb.8': 'Frame',
  'edit.rb.9': 'Tracks / clips',
  'edit.rb.10': 'Arrangement stays on this page only and is not saved.',
  'edit.rb.11': 'Video / audio / subtitles in parallel',
  'edit.rb.12': 'Tools',
  'edit.rb.13': 'Cut',
  'edit.rb.14': 'Drag shots or audio here to start editing, or send them over from the Video page in one click.',
  'edit.rb.15': 'Import media',
  'edit.rb.16': 'Clip inspector',
  'edit.rb.17': 'Name',
  'edit.rb.18': 'Track',
  'edit.rb.19': 'In point',
  'edit.rb.20': 'Out point',
  'edit.rb.21': 'Speed',
  'edit.rb.22': 'Volume',
  'edit.rb.23': 'Opacity',
  'edit.rb.24': 'Back to timeline',
  'edit.rb.25': 'Place on timeline',
  'edit.rb.26': 'Nothing to preview yet',
  'edit.rb.27': 'Select a clip to view it here',
  'edit.rb.28': 'Media pool items',
  'edit.rb.29': 'Cut the selected clip at the playhead (C)',
  'edit.rb.30': 'Mute',
  'edit.rb.31': 'Lock',
  'edit.rb.32': 'Placing on the timeline references the file; it is not copied',
  'edit.rb.33': 'Pause',
  'edit.rb.34': 'Play',
  'edit.rb.35': 'Snap on · align to clip edges',
  'edit.rb.36': 'Snap off',
  'edit.rb.37': 'Click a clip to see its in/out points and volume.',
  'edit.rb.38': 'Click a clip to see its in/out points.',
  'edit.rb.39': 'Shortcuts: Space play · I in point · O out point · C cut',
  'edit.rb.40': 'In',
  'edit.rb.41': 'Out',
  'edit.rb.42': 'Subtitles',
  'edit.rb.43': 'The subtitle track is not connected here yet. Prepare subtitles on the Sound page first.',
  'edit.rb.44': 'No media yet. Send finished items from the Video or Sound page, or drag them in from Assets.',
  'pat.edit.tracksClips': '{n} tracks · {m} clips',
  'pat.edit.monitorClips': '1920×1080 · 24 fps · {n} clips',

  'rough.117': 'Create record was changed in another window; keeping the original request. Will not create or enqueue.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.118': 'Original node, project, permission, or unconfirmed action changed. Close and recheck; will not resend.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.119': 'Current project generation or write permission is unconfirmed; original draft kept.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.120': 'Original enqueue intent changed; cannot restore another request.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.121': 'This browser\'s create intent changed; cannot continue the original request.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.122': 'Original create request or read has been retired.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.123': 'Read or create timed out; result still needs checking; will not resend.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.124': 'Receipt or version for the blank slot does not match; result still needs checking.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.125': 'Enter a valid prompt on the original node first.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.126': 'Original create record is missing.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.127': 'Blank work slot saved; not yet enqueued or generated. Node graph and links remain browser drafts.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.128': 'Blank-slot save result needs checking; keeping original request ID. Will not auto-create or resend.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.129': 'Create intent kept, but dispatch was not confirmed; only recheck the original request. Will not create again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.130': 'This browser\'s create record changed or cannot be verified; create was not sent. Will not switch to another request.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.131': 'Failed to save create intent or conflicted with another window; inputs kept, create not sent.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.132': 'Failed to prepare the formal node slot.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.133': 'Write permission unconfirmed; keeping create intent. Will not restore the queue entry.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.134': 'Current node does not match the kept create intent; cannot restore the link.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.135': 'Blank slot restored from the unique server create record; not yet enqueued, executed, or reviewed.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.136': 'Could not confirm a unique unchanged create result; keeping original request. Will not create or enqueue again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.137': 'Create record cleanup not confirmed; task stays on the original queue. Reopen to recheck.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.138': 'Original node task preview changed; not dispatched.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.139': 'Failed to save enqueue record or it was changed elsewhere; not dispatched. Cannot use another request.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.140': 'Original image enqueue result needs checking; keeping request identity. Will not recreate or execute again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.141': 'Enqueue recovery record was not saved; dispatch stopped. Keep inputs and reopen to check storage.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.142': 'Task receipt or recovery record mismatch; not linked to another request. Recheck explicitly.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.143': 'Enqueue record cannot be verified; original task kept. Will not link another request.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.144': 'Task receipt read, but recovery cleanup not confirmed; will not enqueue again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.145': 'Original recovery record changed; cannot publish the task link.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.146': 'Checking original image enqueue result; will not create or dispatch again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.147': 'Write permission unconfirmed; cannot restore the task entry.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.148': 'Current node does not match the original enqueue intent.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.149': 'This production client cannot read the original enqueue request; keep the original record.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.150': 'Blank-slot create record is corrupted; cannot replace its link.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.151': 'Original canvas version changed; cannot restore to another slot.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.152': 'Original task link save was not confirmed.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.153': 'Original enqueue recovery was not confirmed complete.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.154': 'Restored the current production task record; did not re-enqueue, execute, or review. Execution needs a fresh check and confirm.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.155': 'Original enqueue result still needs checking; missing or changed results cannot be resent.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.156': 'Reviewed task version changed; read again and recheck.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.157': 'Blank work slot or generation changed; candidate kept. Will not adopt into another slot.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.158': 'Formal review source check failed.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.159': 'Formal asset pin changed; please recheck.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.160': 'Formal node asset position saved. You can explicitly read the saved slot to verify; the browser draft did not become a shared canvas.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.161': 'Node adoption result needs checking; only read the original record. Will not auto-adopt or resend.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.162': 'Formal node adoption did not finish.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.163': 'An original enqueue request still needs checking; use that request\'s check entry. Will not guess from the list.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.164': 'Many records for the same node; check by task ID from the original list. Will not guess the slot.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.165': 'Generation or current version of the saved slot is unconfirmed.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.166': 'Original node records loaded; pick one explicitly to view. No execute, review, or re-adopt.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.167': 'Read finished; no recoverable same-node tasks. Saved slots follow only explicit server receipts shown here.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.168': 'Failed to read original node slot; will not resend.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.169': 'Formal asset link saved', // [HERMIA-FE-20261031 VERA-EN]
  'rough.170': 'Blank slot; asset not adopted yet', // [HERMIA-FE-20261031 VERA-EN]
  'rough.171': 'Reloaded node, current position, formal task source, and exact asset pin from the server canvas; no execute, review, or re-adopt.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.172': 'Opened original node task; read-only restore with no execute or adopt.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.173': 'Server node asset link', // [HERMIA-FE-20261031 VERA-EN]
  'rough.174': 'Production task permission or identity changed; reopen the project.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.175': 'Cutout delivery format (optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.176': 'Local stationary-noise denoise (optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.177': 'Upscale factor', // [HERMIA-FE-20261031 VERA-EN]
  'rough.178': 'Width (64–2048)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.179': 'Height (64–2048)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.180': 'Sample steps (1–150)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.181': 'Seed (0–2147483647)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.182': 'Negative prompt', // [HERMIA-FE-20261031 VERA-EN]
  'rough.183': 'Image size', // [HERMIA-FE-20261031 VERA-EN]
  'rough.184': 'Image quality', // [HERMIA-FE-20261031 VERA-EN]
  'rough.185': 'Denoising strength (>0 to 1, optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.186': 'Duration (1–600 s)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.187': 'Frame rate (1–60)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.188': 'Voice id', // [HERMIA-FE-20261031 VERA-EN]
  'rough.189': 'Speech rate (0.5–2)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.190': 'Source start (ms)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.191': 'Source end (ms)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.192': 'Target integrated loudness (-30 to -14 LUFS, optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.193': 'Pre-gain target sample peak (-24 to -1 dBFS, optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.194': 'Gain (-60–12 dB, optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.195': 'Output sample rate (8000–96000 Hz, optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.196': 'Output channels (optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.197': 'Standalone audio delivery format (optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.198': 'Fade-in (ms, optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.199': 'Fade-out (ms, optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.200': 'Media production and review', // [HERMIA-FE-20261031 VERA-EN]
  'rough.201': 'This entry only shows the original task status and metadata receipt. Status is fetched only when you explicitly read; no auto request, poll, or task actions.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.202': 'Confirm preview, enqueue, execute, and review separately. Candidates stay private until manual review, then enter the library. Full local acceptance is still pending (LOCAL_REQUIRED).', // [HERMIA-FE-20261031 VERA-EN]
  'rough.203': 'Explicitly check the original image enqueue result from the original node; will not replace it with the latest list item.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.204': 'Use “Read task list” to find saved receipts.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.205': 'Explicitly choose “image-to-video” or “video-to-video”, with matching source kind and an empty source slot. Whether video-to-video can run still follows the service; the current local route does not run reference video.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.206': 'Current operation is “multi-reference image”: pick a provider config that supports it, append references up to the limit (max five), new weight 1, keep existing weights, purposes, and notes.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.207': 'Below, explicitly choose “reference image-to-image” or “multi-reference image”. The former uses the base-image input rules; the latter appends weighted references.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.208': 'Media production inputs', // [HERMIA-FE-20261031 VERA-EN]
  'rough.209': 'Original comic-panel image request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.210': 'Original storyboard speech request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.211': 'Original storyboard video request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.212': 'Original storyboard image request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.213': 'Bottom layer', // [HERMIA-FE-20261031 VERA-EN]
  'rough.214': 'Top layer', // [HERMIA-FE-20261031 VERA-EN]
  'rough.215': 'Reference configs list local first and label cloud items. Choosing a config switches the production route and clears old permission; cloud send still needs a separate confirm.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.216': 'Local configs are shown first; you can switch to cloud or back. Switching does not send inputs, run a model, or auto-pick a provider.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.217': 'Local', // [HERMIA-FE-20261031 VERA-EN]
  'rough.218': 'Cloud', // [HERMIA-FE-20261031 VERA-EN]
  'rough.219': 'No matching config yet; finish provider and model setup first.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.220': 'Weights normalize mixed reference pixels for init; they do not mean character or style recognition quality.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.221': 'This route uses single-image initialization.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.222': 'Pick 1–5', // [HERMIA-FE-20261031 VERA-EN]
  'rough.223': 'Pick 2', // [HERMIA-FE-20261031 VERA-EN]
  'rough.224': 'Pick 1', // [HERMIA-FE-20261031 VERA-EN]
  'rough.225': 'This config declares end-frame support; start and end frames bind two different formal image versions (id, version, SHA-256) to one request, and the adapter receives both image byte payloads.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.226': 'This config only offers single-image init and does not declare an end-frame protocol. You may use only the start frame; choosing an end frame makes preview refuse explicitly—no silent drop or downgrade.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.227': 'Not selected yet', // [HERMIA-FE-20261031 VERA-EN]
  'rough.228': 'Pick 1–5 reference images; see the recipe for the current service limit.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.229': 'Base image is bound separately; you may also pick helper references the recipe supports.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.230': 'Local trim outputs lossy MP3, clips 10 ms–120 s. Needs installed libmp3lame; 32000–48000 Hz fixed 128 kb/s, lower supported rates fixed 64 kb/s. Supports 8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000 Hz; blank means 48000 Hz stereo. Decoding as S16 does not mean lossless.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.231': 'Local trim outputs processed S16 FLAC. Clips up to 120 s; in/out must fall within the real source duration. Apply chosen gain, rate, and channels first, then lossless compress.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.232': 'Local trim outputs PCM 16-bit WAV. Clips up to 120 s; in/out must fall within the real source duration. Leave optionals blank for original behavior: no gain, 48000 Hz, stereo. High gain may clip.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.233': 'Only parameters supported by the selected config are listed; blank optionals use the provider default.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.234': 'Pick a provider first, then fill parameters it supports.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.235': 'Original task input confirmation gate', // [HERMIA-FE-20261031 VERA-EN]
  'rough.236': 'Pre-enqueue check: save this task only, do not execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.237': 'Pre-execute recheck: use the enqueued task\'s actual command, recipe, and versions.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.238': 'Production preview confirmation', // [HERMIA-FE-20261031 VERA-EN]
  'rough.239': 'Local CPU dual-layer PNG composite', // [HERMIA-FE-20261031 VERA-EN]
  'rough.240': 'Local CPU binary-mask cutout', // [HERMIA-FE-20261031 VERA-EN]
  'rough.241': 'Local trim', // [HERMIA-FE-20261031 VERA-EN]
  'rough.242': 'Original media task records', // [HERMIA-FE-20261031 VERA-EN]
  'rough.243': 'Multi-track composite', // [HERMIA-FE-20261031 VERA-EN]
  'rough.244': 'Current media task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.245': 'Prompt confirmed on the original task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.246': 'Not set explicitly', // [HERMIA-FE-20261031 VERA-EN]
  'rough.247': 'This request explicitly allowed it', // [HERMIA-FE-20261031 VERA-EN]
  'rough.248': 'This request did not allow it', // [HERMIA-FE-20261031 VERA-EN]
  'rough.249': 'No result receipt digest yet', // [HERMIA-FE-20261031 VERA-EN]
  'rough.250': 'Audio actual output measurement', // [HERMIA-FE-20261031 VERA-EN]
  'rough.251': 'Server MP3 stream info and gapless decode check', // [HERMIA-FE-20261031 VERA-EN]
  'rough.252': 'Server FLAC stream info and PCM decode check', // [HERMIA-FE-20261031 VERA-EN]
  'rough.253': 'Server PCM decode measurement receipt', // [HERMIA-FE-20261031 VERA-EN]
  'rough.254': '16-bit S16 FLAC', // [HERMIA-FE-20261031 VERA-EN]
  'rough.255': '16-bit PCM WAV', // [HERMIA-FE-20261031 VERA-EN]
  'rough.256': 'Integrated loudness measurement evidence', // [HERMIA-FE-20261031 VERA-EN]
  'rough.257': 'Denoise actual byte proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.258': 'Sample-peak actual proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.259': 'Above is the decoded measurement of the actual MP3; MP3 is lossy. The decode digest identifies this output and does not prove identity with the source or audio quality. Candidates still need check and manual review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.260': 'Above is the server decode measurement of the actual FLAC; lossless compression after S16 processing does not mean the source was unchanged. Still read actual bytes, check digests, and review manually.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.261': 'Above checks actual WAV sample peak and the computed correction; it does not mean LUFS, true-peak, or subjective quality. Still read bytes, check digests, and review manually.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.262': 'Above is the server decode measurement of the actual WAV; it does not mean gain was measured. Still read bytes, check digests, and review manually.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.263': 'Prior dispatch result is uncertain; only explicit reads of original task status are allowed here. This entry cannot redispatch or discard results.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.264': 'Prior dispatch result is uncertain; execute again is blocked. For the same original task, only continue reading/checking or discard the local result.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.265': 'Original review may already be submitted; only explicit status reads are allowed here. This entry cannot open candidates or continue review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.266': 'Original review may already be submitted. Read the task and candidate first, then confirm the original review; will not regenerate.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.267': 'Local composite controls while running', // [HERMIA-FE-20261031 VERA-EN]
  'rough.268': 'Local cutout controls while running', // [HERMIA-FE-20261031 VERA-EN]
  'rough.269': 'Execute uses only the command, route, and versions saved on the original task; it does not create a new task. After recheck you must still confirm explicitly—no auto dispatch.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.270': 'Execute uses the command saved on the Job below; editing the draft above does not overwrite it. Recheck retires the draft preview; you must still confirm explicitly—no auto dispatch.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.271': 'Explicitly cancel local composite or discard candidate', // [HERMIA-FE-20261031 VERA-EN]
  'rough.272': 'Explicitly cancel local cutout or discard candidate', // [HERMIA-FE-20261031 VERA-EN]
  'rough.273': 'Explicitly cancel local render', // [HERMIA-FE-20261031 VERA-EN]
  'rough.274': 'Discard unused local result', // [HERMIA-FE-20261031 VERA-EN]
  'rough.275': 'Cancel asks the original local process to stop, or revokes adopt rights on an unreviewed candidate; keeps the original record. Will not reprocess or ingest.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.276': 'Timeline cancel asks the original local render to stop or revokes adopt rights on an unreviewed candidate, keeping the receipt and any candidate; reviewed or ingested results cannot be cancelled here.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.277': 'Discard only revokes rights on the local adopt result and keeps the record; remote compute may continue.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.278': 'Media candidate preview and review', // [HERMIA-FE-20261031 VERA-EN]
  'rough.279': 'Image candidate for this task verified by digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.280': 'Video candidate for this task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.281': 'Audio candidate for this task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.282': 'Text to image', // [HERMIA-FE-20261031 VERA-EN]
  'rough.283': 'Image to image', // [HERMIA-FE-20261031 VERA-EN]
  'rough.284': 'Text to video', // [HERMIA-FE-20261031 VERA-EN]
  'rough.285': 'Image to video', // [HERMIA-FE-20261031 VERA-EN]
  'rough.286': 'Video to video', // [HERMIA-FE-20261031 VERA-EN]
  'rough.287': 'Speech synthesis', // [HERMIA-FE-20261031 VERA-EN]
  'rough.288': 'Music generation', // [HERMIA-FE-20261031 VERA-EN]
  'rough.289': 'Sound effects', // [HERMIA-FE-20261031 VERA-EN]
  'rough.290': 'Local audio trim', // [HERMIA-FE-20261031 VERA-EN]
  'rough.291': 'Multi-reference image', // [HERMIA-FE-20261031 VERA-EN]
  'rough.292': 'Image inpaint', // [HERMIA-FE-20261031 VERA-EN]
  'rough.293': 'Local model image upscale', // [HERMIA-FE-20261031 VERA-EN]
  'rough.294': 'Local binary-mask cutout', // [HERMIA-FE-20261031 VERA-EN]
  'rough.295': 'Local dual-layer PNG composite', // [HERMIA-FE-20261031 VERA-EN]
  'rough.296': 'Queued, not executed yet', // [HERMIA-FE-20261031 VERA-EN]
  'rough.297': 'Running', // [HERMIA-FE-20261031 VERA-EN]
  'rough.298': 'Dispatch intent recorded', // [HERMIA-FE-20261031 VERA-EN]
  'rough.299': 'Remote processing', // [HERMIA-FE-20261031 VERA-EN]
  'rough.300': 'Result ready, awaiting local check', // [HERMIA-FE-20261031 VERA-EN]
  'rough.301': 'Awaiting manual review', // [HERMIA-FE-20261031 VERA-EN]
  'rough.302': 'Done, needs check and review', // [HERMIA-FE-20261031 VERA-EN]
  'rough.303': 'Review submit pending check', // [HERMIA-FE-20261031 VERA-EN]
  'rough.304': 'Approved into library', // [HERMIA-FE-20261031 VERA-EN]
  'rough.305': 'Dispatch result uncertain', // [HERMIA-FE-20261031 VERA-EN]
  'rough.306': 'Execution failed', // [HERMIA-FE-20261031 VERA-EN]
  'rough.307': 'Local result discarded', // [HERMIA-FE-20261031 VERA-EN]
  'rough.308': 'Explicitly pick a provider config that supports the current image-reference operation.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.309': 'Reference asset unavailable; reload assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.310': 'Base image cannot also be a helper reference; pick a different asset.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.311': 'A base image or mask is already bound; adjust it with the original input controls.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.312': 'This asset is already bound; remove or adjust it explicitly with the original controls. Will not overwrite existing binds.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.313': 'Current inputs cannot safely append; adjust with the original input controls first.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.314': 'Reference count exceeds the current route limit.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.315': 'Pick an existing lossless WebP recipe.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.316': 'Pick an existing local denoise recipe.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.317': 'Standalone audio format: choose FLAC or MP3, or leave blank for default WAV.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.318': 'Negative prompt exceeds the length limit.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.319': 'Enter a valid voice id.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.320': 'Image size is not supported.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.321': 'Image quality is not supported.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.322': 'Upscale factor must be explicitly 2 or 4.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.323': 'Target integrated loudness must be -30 to -14 LUFS.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.324': 'Target sample peak must be -24 to -1 dBFS.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.325': 'Gain must be a finite number between -60 and 12 dB.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.326': 'Denoising strength must be >0 and ≤1.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.327': 'Speech rate must be between 0.5 and 2.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.328': 'Check parameter ranges and enter finite integers.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.329': 'Image width and height must be multiples of 8.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.330': 'Denoise needs at least 1 s of PCM16 WAV; cannot combine format conversion, normalization, non-zero gain, or fades.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.331': 'Loudness match needs at least 3 s of PCM16 WAV; cannot combine peak target, non-zero manual gain, or fades.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.332': 'Peak normalization currently supports PCM16 WAV output only.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.333': 'Target sample peak plus manual gain must not exceed -1 dBFS.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.334': 'Width and height must both be filled or both left blank.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.335': 'Explicitly choose 2× or 4× upscale first.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.336': 'Trim needs start/end ms; end must be greater than start; clip max 120 s.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.337': 'Fade-in plus fade-out cannot exceed the trimmed clip length.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.338': 'Chosen duration, sample rate, and channels would exceed the 25 MiB output cap; adjust and preview again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.339': 'MP3 clips must be at least 10 ms to keep accurate decode duration.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.340': 'MP3 sample rate only supports 8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000 Hz; change explicitly—no auto resample.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.341': 'Explicitly pick a config on the selected local or cloud route.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.342': 'Pick the provider and model from the current config.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.343': 'Selected config does not support some filled parameters; clear them explicitly or restore the previous choice.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.344': 'Enter this run\'s prompt, up to 16000 characters.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.345': 'Upscale needs a local service that is currently enabled.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.346': 'Before using cloud, explicitly confirm sending this prompt and reference assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.347': 'Only image-to-video can bind start and end frames.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.348': 'Current config does not support end frames; pick one that does. Will not silently drop the end frame or fall back to single image.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.349': 'Pick the start frame before the end frame.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.350': 'Start and end frames cannot be the same image.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.351': 'Pick a PNG source first, then explicitly pick the binary mask drawn for that version.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.352': 'Source asset version changed; reselect the current version.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.353': 'Pick the required number of image sources.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.354': 'Pick one source asset of the matching kind.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.355': 'This operation does not accept asset references.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.356': 'Source and license note exceeds the length limit.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.357': 'This route has no verified image-input contract; explicitly pick a config that supports the operation.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.358': 'Total of base and reference images exceeds the current route limit.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.359': 'Reference weight must be >0 and ≤1.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.360': 'This route does not provide a keep/repaint contract for this hand-drawn mask.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.361': 'Layer opacity must be an integer 0–255.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.362': 'Composite accepts saved PNGs of at most 8 MiB each.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.363': 'Original node prompt, position, or local route changed; prepare the node task again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.364': 'Please check the inputs.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.365': 'This input check expired or was already used; read the preview again and confirm explicitly. No redispatch.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.366': 'Identity, permission, or project entry changed; reopen the current project.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.367': 'Resume task request, execution record, or version changed; return to the original task entry to recheck.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.368': 'Original task receipt read; linked view refresh did not finish.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.369': 'Source kind, version, or digest changed, or it was deleted; will not replace with the latest version.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.370': 'Draft, service config, or edit state changed; please recheck.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.371': 'Current asset list has not been verified for the same version; explicitly read current asset versions and retry.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.372': 'Current inputs cannot safely append.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.373': 'A source is already bound; remove it with the original input controls first. Will not overwrite.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.374': 'A base image exists or the route input limit is exceeded; adjust with the original input controls first.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.375': 'Failed to read the handoff asset; draft unchanged.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.376': 'PNG source unavailable; reload assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.377': 'Start-frame source unavailable; reload assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.378': 'Image source unavailable; reload assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.379': 'Reference asset is bound as a helper input; remove that reference explicitly before choosing a base image.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.380': 'Source unavailable; reload assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.381': 'Pick at most five reference images.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.382': 'Current config does not support end frames; pick one that supports start and end frames.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.383': 'End-frame source unavailable; reload assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.384': 'Mask does not match the current source version; reload assets.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.385': 'Selected source was deleted or is unavailable; remove it first.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.386': 'End-frame source was deleted or is unavailable; remove the end frame first.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.387': 'Original provider-config read entry has been retired.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.388': 'Failed to read provider configs.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.389': 'Original production entry has been retired; did not read a new-task preview.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.390': 'Composite recipe or sources changed.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.391': 'Provider route changed; reload configs and preview again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.392': 'Preview read; task not created and media not executed yet.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.393': 'Production preview did not finish.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.394': 'Original production entry has been retired; task not created.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.395': 'Original preview or task scope changed; task not created.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.396': 'Original node enqueue was retired; send did not continue.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.397': 'Original image enqueue timed out; result still needs checking.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.398': 'Enqueue receipt does not match the preview; read the task to check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.399': 'Enqueue command, route, or recipe does not match the original preview; read to check. Cannot execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.400': 'Task saved to the queue. Execution still needs a separate click.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.401': 'Original image enqueue result needs checking; will not create or execute again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.402': 'Enqueue did not finish; read to check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.403': 'Original task-list entry has been retired.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.404': 'Original image task does not match the current comic-panel request; read the original receipt.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.405': 'Original speech task does not match the current storyboard dialogue request; read the original receipt.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.406': 'Found a saved record for the original request; will not recreate or execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.407': 'Original request receipt not found yet. Keep the uncertain state; do not resend.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.408': 'Failed to read the task list.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.409': 'Original resume entry has been retired; did not read other tasks.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.410': 'Original task does not match the current storyboard request; read that request\'s receipt.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.411': 'Task left the original image-node binding.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.412': 'Current task version read; did not re-execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.413': 'Failed to read the task.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.414': 'Original enqueued audio parameters are outside this card\'s processing scope; cannot re-preview execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.415': 'Original resume entry has been retired; did not recheck execute preview.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.416': 'Reloaded preview does not match the original enqueue command, route, or recipe; cannot execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.417': 'Checked the original enqueue preview; still need a separate confirm for this execute input. No dispatch.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.418': 'Failed to check the original enqueue preview.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.419': 'Original resume entry has been retired; no action sent.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.420': 'Original task scope or version changed; execute not dispatched.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.421': 'Original task response version or identity mismatch; read again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.422': 'Recorded a request to stop the local render; reread the original task to check. Existing receipt and candidate kept; cannot continue adopting.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.423': 'Revoked adopt rights on this unreviewed timeline result; original receipt and candidate kept.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.424': 'Recorded local cancel and revoked candidate adopt rights; read the original task to check. Will not auto-retry.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.425': 'Discarded adopt rights on the local result; remote compute may continue.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.426': 'Review receipt saved; check the current asset library.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.427': 'Checked local interrupt status; did not resubmit media generation.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.428': 'Task receipt received; check status and candidate results.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.429': 'Review was saved, but asset-list refresh did not finish; read again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.430': 'Operation result unconfirmed; read the task to check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.431': 'Original cutout task receipt mismatch; read again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.432': 'Original task recorded cancel; local processing and candidate adopt are fenced. Will not auto-retry.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.433': 'Read original local cutout task status; did not re-execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.434': 'Original local task control result unconfirmed; wait for execute to return, then read to check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.435': 'Original candidate-read entry has been retired; media not read.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.436': 'Candidate media kind or size is incorrect; read the task to check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.437': 'Local cutout candidate does not match processing proof; cannot review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.438': 'Audio timeline WAV candidate does not match the bound output config or actual measurement; cannot review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.439': 'Local WAV candidate does not match actual output measurement; cannot review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.440': 'Local FLAC candidate does not match actual output measurement; cannot review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.441': 'Local MP3 candidate does not match actual output measurement; cannot review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.442': 'Candidate byte digest does not match the task receipt; cannot review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.443': 'Failed to read candidate media.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.444': 'Candidate media cannot be shown or played. Read the original task to check; cannot review now.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.445': 'Local receipt download did not finish; reread the task before downloading again.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.446': 'Original task status, request, or version cannot be used as a follow-on resume record; reread to check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.447': 'Asset handoff cancelled; draft unchanged.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.448': 'Current identity or project scope needs checking.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.449': 'Character', // [HERMIA-FE-20261031 VERA-EN]
  'rough.450': 'Outfit', // [HERMIA-FE-20261031 VERA-EN]
  'rough.451': 'Environment', // [HERMIA-FE-20261031 VERA-EN]
  'rough.452': 'Style', // [HERMIA-FE-20261031 VERA-EN]
  'rough.453': 'Composition', // [HERMIA-FE-20261031 VERA-EN]
  'rough.454': 'Image source, weight, or mask binding is invalid; check the current asset version.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.455': 'Image source or mask receipt is incomplete; read the original record to check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.456': 'This production client lacks original-request read; keep the record. Will not guess from the list or re-enqueue.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.457': 'Enqueue input kept in this session', // [HERMIA-FE-20261031 VERA-EN]
  'rough.458': 'Original prompt at enqueue', // [HERMIA-FE-20261031 VERA-EN]
  'rough.459': 'These inputs stay in this session only; the browser recovery hint stores identity and digest only.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.460': 'Canvas and node', // [HERMIA-FE-20261031 VERA-EN]
  'rough.461': 'Saved coordinates', // [HERMIA-FE-20261031 VERA-EN]
  'rough.462': 'Formal asset pin', // [HERMIA-FE-20261031 VERA-EN]
  'rough.463': 'Saved source prompt digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.464': 'Original production task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.465': 'Original server canvas', // [HERMIA-FE-20261031 VERA-EN]
  'rough.466': 'Adopt asset only', // [HERMIA-FE-20261031 VERA-EN]
  'rough.467': '(read-only; will not resend from here)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.468': '(current browser draft may have changed)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.469': 'to node', // [HERMIA-FE-20261031 VERA-EN]
  'rough.470': 'Default PNG, keep original request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.471': 'Lossless WebP · keep transparent pixels', // [HERMIA-FE-20261031 VERA-EN]
  'rough.472': 'Off, keep original request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.473': 'Stationary noise · local FFT denoise', // [HERMIA-FE-20261031 VERA-EN]
  'rough.474': 'Default WAV, keep original request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.475': 'FLAC · processed S16 lossless', // [HERMIA-FE-20261031 VERA-EN]
  'rough.476': 'MP3 · lossy (CBR)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.477': 'Explicitly choose a factor', // [HERMIA-FE-20261031 VERA-EN]
  'rough.478': '2×', // [HERMIA-FE-20261031 VERA-EN]
  'rough.479': '4×', // [HERMIA-FE-20261031 VERA-EN]
  'rough.480': 'Default stereo (2)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.481': 'Mono (1)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.482': 'Stereo (2)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.483': 'Use provider default', // [HERMIA-FE-20261031 VERA-EN]
  'rough.484': 'Result not confirmed yet; further sends blocked. Read the original task to check; will not auto-retry.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.485': 'This version already has a send record. The same action will not send again; keep reading the original record.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.486': 'Original request pending check:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.487': 'This node entry lacks recoverable enqueue; cannot create a task. Reopen from the original node.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.488': 'Read-only resume of the original task: explicitly read status or download the JSON just read. This entry cannot preview, execute, reconcile interrupt, cancel, or review; status progress does not mean reviewed into the library.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.489': 'Resume-only of the original task; does not create or re-queue. This entry does not open candidate media, manual review, or adopt; status progress does not mean reviewed into the library.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.490': 'Read-only resume of original node task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.491': 'Inputs are fixed to the command saved on the task below; version and status come from the receipt. Provider config, candidates, and all task actions stay closed here.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.492': 'Resume-only of original node task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.493': 'Inputs are fixed to the command saved on the task below. After reloading provider config and execute preview, still confirm this execute impact separately; no auto dispatch.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.494': 'Reload original task provider config', // [HERMIA-FE-20261031 VERA-EN]
  'rough.495': 'Inputs come from verified original source versions; to change parameters return to the original entry and prepare a new request. Preview, enqueue, execute, and review still confirm separately.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.496': 'Check full sources and inputs', // [HERMIA-FE-20261031 VERA-EN]
  'rough.497': 'Explicitly read provider config for this request', // [HERMIA-FE-20261031 VERA-EN]
  'rough.498': 'Read production preview', // [HERMIA-FE-20261031 VERA-EN]
  'rough.499': 'Close this request view; keep the original task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.500': 'Production inputs', // [HERMIA-FE-20261031 VERA-EN]
  'rough.501': 'Operation', // [HERMIA-FE-20261031 VERA-EN]
  'rough.502': 'Local CPU uses a saved hand-drawn binary mask: white keeps source pixels; black becomes transparent with color cleared. Default same-size PNG, or explicitly choose lossless WebP (re-decode checks all RGBA). No provider, model, prompt, or cloud. Accepts only 64–1024 PNGs with sides multiples of 8, and matching masks; bytes are rechecked at execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.503': 'Dual-layer PNG · bottom to top', // [HERMIA-FE-20261031 VERA-EN]
  'rough.504': 'Pick two same-size saved PNGs (64–1024, sides multiples of 8, ≤8 MiB each). Straight-alpha source-over on encoded values; final integer rounding; fully transparent pixels clear RGB. No color-profile conversion or model call. Hidden layers still check original source permission and version.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.505': 'Swap layers', // [HERMIA-FE-20261031 VERA-EN]
  'rough.506': 'Creates only the composite recipe on the original Job. After explicit execute, a private PNG candidate is made; check and review before saving a formal version.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.507': 'Production route', // [HERMIA-FE-20261031 VERA-EN]
  'rough.508': 'Provider and model', // [HERMIA-FE-20261031 VERA-EN]
  'rough.509': 'Explicitly choose the current config', // [HERMIA-FE-20261031 VERA-EN]
  'rough.510': 'Reload configs', // [HERMIA-FE-20261031 VERA-EN]
  'rough.511': 'Prompt for this run', // [HERMIA-FE-20261031 VERA-EN]
  'rough.512': 'I confirm allowing this prompt and selected references to be sent to that cloud service; fees may apply', // [HERMIA-FE-20261031 VERA-EN]
  'rough.513': 'No usable source of this kind in the library.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.514': 'Source changed or unavailable; reselect versions before preview.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.515': 'Explicitly select current source versions', // [HERMIA-FE-20261031 VERA-EN]
  'rough.516': 'Remove selected sources', // [HERMIA-FE-20261031 VERA-EN]
  'rough.517': 'Video start/end frames · real dual-image bind', // [HERMIA-FE-20261031 VERA-EN]
  'rough.518': 'End frame (optional)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.519': 'No end frame; start frame only', // [HERMIA-FE-20261031 VERA-EN]
  'rough.520': 'First explicitly pick the start frame in image sources below.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.521': 'Current config declares no end-frame support; preview will refuse. Clear the end frame or pick a dual-image config.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.522': 'Clear end frame', // [HERMIA-FE-20261031 VERA-EN]
  'rough.523': 'Saved hand-drawn binary mask', // [HERMIA-FE-20261031 VERA-EN]
  'rough.524': 'Uses the original hand-drawn mask: white keeps the image; black is repainted. Backend converts semantics and protects white; image and mask versions must match. Result stays a private candidate needing manual review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.525': 'Mask bound to the current source version', // [HERMIA-FE-20261031 VERA-EN]
  'rough.526': 'Explicitly pick a verified mask', // [HERMIA-FE-20261031 VERA-EN]
  'rough.527': 'Pick a PNG source first, then the mask saved for that version.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.528': 'No usable hand-drawn mask for this source version. In the asset workspace pick the source, draw and save a binary mask, then read current asset versions.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.529': 'Source or mask changed, deleted, or lost verification. Old preview and confirm are invalid; reload and explicitly pick current versions.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.530': 'Image references and weights · exact versions', // [HERMIA-FE-20261031 VERA-EN]
  'rough.531': 'Purpose not set', // [HERMIA-FE-20261031 VERA-EN]
  'rough.532': 'Explicitly select current reference versions', // [HERMIA-FE-20261031 VERA-EN]
  'rough.533': 'Remove image input binds', // [HERMIA-FE-20261031 VERA-EN]
  'rough.534': 'Bound image versions changed; old preview and confirm are invalid. Reselect explicitly.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.535': 'Reference video purpose', // [HERMIA-FE-20261031 VERA-EN]
  'rough.536': 'Ordinary video source', // [HERMIA-FE-20261031 VERA-EN]
  'rough.537': 'Style reference', // [HERMIA-FE-20261031 VERA-EN]
  'rough.538': 'Action reference', // [HERMIA-FE-20261031 VERA-EN]
  'rough.539': 'Camera reference', // [HERMIA-FE-20261031 VERA-EN]
  'rough.540': 'The original image version goes through the enabled local upscale model, then to the chosen factor PNG size. Max output 4096×4096, 25 MiB; still needs manual review. Does not download or start models; model quality and local inference are not accepted yet.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.541': 'Depth / Pose / Edge / Mask / Layout control adapters keep boundaries only; execute is not offered yet.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.542': 'Processing parameters', // [HERMIA-FE-20261031 VERA-EN]
  'rough.543': 'Fade-in/out use linear volume relative to the trimmed clip start/end; their sum cannot exceed clip length. Leave blank to keep the original request; explicit 0 means no fade. Gain first, then fades, then sample-rate/channel conversion.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.544': 'Sample-peak normalization supports PCM16 WAV source and output only; rate and channels must match the source; ms points must land on full sample frames. Measures the selected segment only; target is before manual gain and fades; correction range -60 to +12 dB; silence and out-of-range requests are refused. Target plus manual gain must stay ≤ -1 dBFS; fades may lower the actual peak further. Not LUFS or true-peak. Leave blank for original behavior.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.545': 'Integrated loudness match: at least 3 s PCM16 WAV at the same rate/channels; mutually exclusive with peak target, non-zero manual gain, and fades. Measure the segment, apply fixed gain -60 to +12 dB, remeasure; error ≤0.2 LU; keep -1 dBTP true-peak headroom. Refuse if unsafe; no limiter. Leave blank for original behavior.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.546': 'Stationary-noise denoise: at least 1 s PCM16 WAV same rate/channels. Fixed FFT recipe on the segment; no model; cannot combine format conversion, normalization, non-zero gain, or fades. May affect detail—listen then review; measurements do not mean better listening quality.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.547': 'Explicitly clear unsupported parameters', // [HERMIA-FE-20261031 VERA-EN]
  'rough.548': 'Source and license note', // [HERMIA-FE-20261031 VERA-EN]
  'rough.549': 'Clear local inputs', // [HERMIA-FE-20261031 VERA-EN]
  'rough.550': 'This card task lacks a verifiable persistent scope and storage generation; cannot create or execute. Re-enter from the original saved card.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.551': 'Confirm this preview', // [HERMIA-FE-20261031 VERA-EN]
  'rough.552': 'Preview binds current inputs, source versions, and processing interface. Create only saves the task; does not execute yet.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.553': 'Check this execute interface, defaults, and workflow', // [HERMIA-FE-20261031 VERA-EN]
  'rough.554': 'This preview\'s interface record; does not mean processing succeeded.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.555': 'I checked this run\'s inputs, sources, and processing boundary', // [HERMIA-FE-20261031 VERA-EN]
  'rough.556': 'Create task and enqueue only', // [HERMIA-FE-20261031 VERA-EN]
  'rough.557': 'Task records', // [HERMIA-FE-20261031 VERA-EN]
  'rough.558': 'This entry only resumes this one original node task. To pick another, return to the task center and recheck.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.559': 'Read task list', // [HERMIA-FE-20261031 VERA-EN]
  'rough.560': 'After reading you can pick a saved task; will not auto-create or execute.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.561': 'Saved tasks', // [HERMIA-FE-20261031 VERA-EN]
  'rough.562': 'Select an original task record', // [HERMIA-FE-20261031 VERA-EN]
  'rough.563': 'Confirmed inputs and processing record for this task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.564': 'Shows the public server receipt just read; does not replace current production inputs or mean local capability acceptance passed.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.565': 'Original task is local CPU dual-layer PNG composite. Layer order, visibility, and opacity stay in the confirmed recipe below; no model or cloud.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.566': 'Original task is local CPU binary-mask cutout with no provider, model, prompt, or cloud send. Source order: original image, then hand-drawn mask.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.567': 'Original prompt', // [HERMIA-FE-20261031 VERA-EN]
  'rough.568': 'Original task parameters', // [HERMIA-FE-20261031 VERA-EN]
  'rough.569': 'Original request did not set processing parameters explicitly; actual processing follows the execute interface record and receipt.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.570': 'Original source and license note', // [HERMIA-FE-20261031 VERA-EN]
  'rough.571': 'This task has no media-production input projection; check its bound original timeline record.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.572': 'Bound route digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.573': 'This task has no external provider route projection.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.574': 'Original request digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.575': 'Original result receipt digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.576': 'Execute interface record and technical summary', // [HERMIA-FE-20261031 VERA-EN]
  'rough.577': 'Confirmed interface, parameter, and workflow records; this metadata does not prove remote results or local acceptance.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.578': 'The original execute entry will recheck the digest:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.579': 'Actual output measurement', // [HERMIA-FE-20261031 VERA-EN]
  'rough.580': 'Media duration', // [HERMIA-FE-20261031 VERA-EN]
  'rough.581': 'Actual size', // [HERMIA-FE-20261031 VERA-EN]
  'rough.582': 'Actual audio', // [HERMIA-FE-20261031 VERA-EN]
  'rough.583': 'Output digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.584': 'Selected PCM SHA256:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.585': 'Output PCM SHA256:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.586': 'Original task measured receipt; candidates still need listening and manual review.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.587': 'FLAC sample and decode proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.588': 'Stream-info MD5:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.589': 'MP3 sample and lossy-decode proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.590': 'Decoded PCM SHA256:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.591': 'Output measurement does not prove fade listening quality or volume envelope; listen to the candidate then review explicitly.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.592': 'Image upscale size and digest proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.593': 'Local CPU processing proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.594': 'Output digest:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.595': 'Dual-layer PNG composite proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.596': 'Decoded RGBA digest:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.597': 'Layer recipe digest:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.598': 'Local lossless WebP processing proof', // [HERMIA-FE-20261031 VERA-EN]
  'rough.599': 'Source versions bound to this task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.600': 'Source digest:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.601': 'This task\'s asset sources changed; cannot continue execute or review. Keep the original record for read/check.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.602': 'Task receipt details', // [HERMIA-FE-20261031 VERA-EN]
  'rough.603': 'Read current task to check', // [HERMIA-FE-20261031 VERA-EN]
  'rough.604': 'Download current read receipt (JSON)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.605': 'Local execute request has not returned. You may read the same original task or cancel explicitly; other production edits stay locked.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.606': 'Read the running original cutout task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.607': 'Explicitly cancel the running original cutout task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.608': 'Read original enqueue preview', // [HERMIA-FE-20261031 VERA-EN]
  'rough.609': 'Explicitly execute the current queued task', // [HERMIA-FE-20261031 VERA-EN]
  'rough.610': 'Check existing remote progress', // [HERMIA-FE-20261031 VERA-EN]
  'rough.611': 'Check interrupt status without resending', // [HERMIA-FE-20261031 VERA-EN]
  'rough.612': 'Candidate result', // [HERMIA-FE-20261031 VERA-EN]
  'rough.613': 'Read and verify candidate media', // [HERMIA-FE-20261031 VERA-EN]
  'rough.614': 'I viewed this candidate and confirm adopting the current task version and output digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.615': 'Explicitly review and add to the asset library', // [HERMIA-FE-20261031 VERA-EN]
  'rough.616': 'Open this task\'s approved asset', // [HERMIA-FE-20261031 VERA-EN]
  'rough.617': 'Original task reviewed into the library. Product milestone acceptance is still LOCAL_REQUIRED.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.618': 'Asset reference handoff to', // [HERMIA-FE-20261031 VERA-EN]
  'rough.619': 'Check', // [HERMIA-FE-20261031 VERA-EN]
  'rough.620': 'Explicitly add', // [HERMIA-FE-20261031 VERA-EN]
  'rough.621': 'Show layer', // [HERMIA-FE-20261031 VERA-EN]
  'rough.622': 'Layer', // [HERMIA-FE-20261031 VERA-EN]
  'rough.623': 'Config reference does not mean the service is verified usable.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.624': 'Current image recipe:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.625': 'Bound source', // [HERMIA-FE-20261031 VERA-EN]
  'rough.626': 'Start frame:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.627': 'End frame:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.628': 'Reference', // [HERMIA-FE-20261031 VERA-EN]
  'rough.629': 'Reference weight ·', // [HERMIA-FE-20261031 VERA-EN]
  'rough.630': 'Reference purpose ·', // [HERMIA-FE-20261031 VERA-EN]
  'rough.631': 'Reference source note ·', // [HERMIA-FE-20261031 VERA-EN]
  'rough.632': 'Local video recipe', // [HERMIA-FE-20261031 VERA-EN]
  'rough.633': 'Selected config does not support filled parameters:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.634': 'Cloud send confirmation:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.635': 'Source timeline', // [HERMIA-FE-20261031 VERA-EN]
  'rough.636': 'Target', // [HERMIA-FE-20261031 VERA-EN]
  'rough.637': 'True peak: input', // [HERMIA-FE-20261031 VERA-EN]
  'rough.638': 'Source version v', // [HERMIA-FE-20261031 VERA-EN]
  'rough.639': 'Local stationary-noise FFT recipe; selected', // [HERMIA-FE-20261031 VERA-EN]
  'rough.640': 'Selected segment RMS:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.641': 'Target before gain and fades:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.642': 'Selected source peak', // [HERMIA-FE-20261031 VERA-EN]
  'rough.643': 'Not yet read a verified', // [HERMIA-FE-20261031 VERA-EN]
  'rough.644': 'Production', // [HERMIA-FE-20261031 VERA-EN]
  'rough.645': 'Check reads metadata only; before adding, recheck the version. Does not change prompt, provider, or parameters, and does not overwrite an existing base image.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.646': 'handoff version', // [HERMIA-FE-20261031 VERA-EN]
  'rough.647': 'bytes', // [HERMIA-FE-20261031 VERA-EN]
  'rough.648': 'production draft', // [HERMIA-FE-20261031 VERA-EN]
  'rough.649': 'handoff', // [HERMIA-FE-20261031 VERA-EN]
  'rough.650': 'layer', // [HERMIA-FE-20261031 VERA-EN]
  'rough.651': 'Layer opacity (0–255)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.652': 'Weight must be >0 and ≤1; initializes pixels per the current recipe with no semantic or style guarantee.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.653': ': node structure checked; real inference not verified yet. 64–1024, sides multiples of 32, 1–10 s, 1–30 fps; output is VP9 WebM rounded to the model frame step. Current local route does not run reference video.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.654': '. These inputs will not be dropped automatically.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.655': 'Original preview digest', // [HERMIA-FE-20261031 VERA-EN]
  'rough.656': 'ms', // [HERMIA-FE-20261031 VERA-EN]
  'rough.657': 'LUFS (tolerance ±0.2 LU).', // [HERMIA-FE-20261031 VERA-EN]
  'rough.658': 'frames.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.659': '(S16). Total RMS change is not denoise quality or SNR.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.660': 'frames. Sample-peak measurement is not LUFS or true-peak.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.661': 'bytes S16', // [HERMIA-FE-20261031 VERA-EN]
  'rough.662': 'ms (including encoder delay and padding)', // [HERMIA-FE-20261031 VERA-EN]
  'rough.663': 'output measurement; original request parameters and execute recipe do not mean actual output.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.664': 'bytes · fully transparent pixels have RGB cleared', // [HERMIA-FE-20261031 VERA-EN]
  'rough.665': '. Input structure checked; real inference not verified. References up to', // [HERMIA-FE-20261031 VERA-EN]
  'rough.666': 'images;', // [HERMIA-FE-20261031 VERA-EN]
  'rough.667': 'sources ·', // [HERMIA-FE-20261031 VERA-EN]
  'rough.668': 'channels ·', // [HERMIA-FE-20261031 VERA-EN]
  'rough.669': 'LUFS; input', // [HERMIA-FE-20261031 VERA-EN]
  'rough.670': 'LUFS → output', // [HERMIA-FE-20261031 VERA-EN]
  'rough.671': 'dBTP → output', // [HERMIA-FE-20261031 VERA-EN]
  'rough.672': 'dBTP; fixed gain', // [HERMIA-FE-20261031 VERA-EN]
  'rough.673': '; selected', // [HERMIA-FE-20261031 VERA-EN]
  'rough.674': 'ms;', // [HERMIA-FE-20261031 VERA-EN]
  'rough.675': 'frames, output', // [HERMIA-FE-20261031 VERA-EN]
  'rough.676': '; output RMS:', // [HERMIA-FE-20261031 VERA-EN]
  'rough.677': 'dBFS; actual correction', // [HERMIA-FE-20261031 VERA-EN]
  'rough.678': '/ 32768; actual output peak', // [HERMIA-FE-20261031 VERA-EN]
  'rough.679': 'samples · decoded', // [HERMIA-FE-20261031 VERA-EN]
  'rough.680': 'bytes S16 · container duration', // [HERMIA-FE-20261031 VERA-EN]
  'rough.681': '× · PNG', // [HERMIA-FE-20261031 VERA-EN]
  'rough.682': '· keep', // [HERMIA-FE-20261031 VERA-EN]
  'rough.683': 'pixels · remove', // [HERMIA-FE-20261031 VERA-EN]
  'rough.684': 'pixels · PNG', // [HERMIA-FE-20261031 VERA-EN]
  'rough.685': 'pixels · WebP', // [HERMIA-FE-20261031 VERA-EN]
  'rough.686': 'candidate · v', // [HERMIA-FE-20261031 VERA-EN]
  'rough.687': 'Subject/style multi-reference: the current video protocol does not declare this capability (multi_reference=false). This panel does not offer reference weights, pixel stitching, segment stitching, or other fake multi-image conditioning; multi-image reference beyond start/end frames stays unsupported.', // [HERMIA-FE-20261031 VERA-EN]

  'rough.688': 'No config for this operation yet: ', // [HERMIA-FE-20261031 VERA-EN]
  'rough.689': ' config; switch route or finish the matching config first — no auto-fallback.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.690': 'Reference weight · ', // [HERMIA-FE-20261031 VERA-EN]
  'rough.691': 'Added to the original video production draft; old preview and cloud confirmation cleared. Not yet prechecked, queued, or executed.', // [HERMIA-FE-20261031 VERA-EN]
  'rough.692': 'Added to the original image production draft; old preview and cloud confirmation cleared. Not yet prechecked, queued, or executed.', // [HERMIA-FE-20261031 VERA-EN]
};

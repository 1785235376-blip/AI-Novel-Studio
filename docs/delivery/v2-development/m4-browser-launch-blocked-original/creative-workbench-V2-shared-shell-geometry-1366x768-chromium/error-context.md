# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: creative-workbench.spec.ts >> V2 shared-shell geometry 1366x768
- Location: tests/visual/creative-workbench.spec.ts:53:117

# Error details

```
Error: browserType.launch: Target page, context or browser has been closed
Browser logs:

<launching> /usr/bin/chromium --disable-field-trial-config --disable-background-networking --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-back-forward-cache --disable-breakpad --disable-client-side-phishing-detection --disable-component-extensions-with-background-pages --disable-component-update --no-default-browser-check --disable-default-apps --disable-dev-shm-usage --disable-edgeupdater --disable-extensions --disable-features=AvoidUnnecessaryBeforeUnloadCheckSync,BoundaryEventDispatchTracksNodeRemoval,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,BlockOriginHeaderModificationOnRedirect,Translate,AutoDeElevate,OptimizationHints,msForceBrowserSignIn,msEdgeUpdateLaunchServicesPreferredVersion --enable-features=CDPScreenshotNewSurface --allow-pre-commit-input --disable-hang-monitor --disable-ipc-flooding-protection --disable-popup-blocking --disable-prompt-on-repost --disable-renderer-backgrounding --disable-updater-scheduler --force-color-profile=srgb --metrics-recording-only --no-first-run --password-store=basic --use-mock-keychain --no-service-autorun --export-tagged-pdf --disable-search-engine-choice-screen --unsafely-disable-devtools-self-xss-warnings --edge-skip-compat-layer-relaunch --disable-infobars --disable-search-engine-choice-screen --disable-sync --enable-unsafe-swiftshader --headless --hide-scrollbars --mute-audio --blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4 --no-sandbox --user-data-dir=/tmp/playwright_chromiumdev_profile-DUw1wP --remote-debugging-pipe --no-startup-window
<launched> pid=58
[pid=58][err] [58:58:1009/225203.107809:ERROR:third_party/crashpad/crashpad/util/file/filesystem_posix.cc:63] mkdir : No such file or directory (2)
[pid=58][err] chrome_crashpad_handler: --database is required
[pid=58][err] Try 'chrome_crashpad_handler --help' for more information.
[pid=58][err] [58:58:1009/225203.244607:FATAL:chrome/browser/process_singleton_posix.cc:297] Check failed: . socket() failed: Operation not permitted (1)
Call log:
  - <launching> /usr/bin/chromium --disable-field-trial-config --disable-background-networking --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-back-forward-cache --disable-breakpad --disable-client-side-phishing-detection --disable-component-extensions-with-background-pages --disable-component-update --no-default-browser-check --disable-default-apps --disable-dev-shm-usage --disable-edgeupdater --disable-extensions --disable-features=AvoidUnnecessaryBeforeUnloadCheckSync,BoundaryEventDispatchTracksNodeRemoval,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,BlockOriginHeaderModificationOnRedirect,Translate,AutoDeElevate,OptimizationHints,msForceBrowserSignIn,msEdgeUpdateLaunchServicesPreferredVersion --enable-features=CDPScreenshotNewSurface --allow-pre-commit-input --disable-hang-monitor --disable-ipc-flooding-protection --disable-popup-blocking --disable-prompt-on-repost --disable-renderer-backgrounding --disable-updater-scheduler --force-color-profile=srgb --metrics-recording-only --no-first-run --password-store=basic --use-mock-keychain --no-service-autorun --export-tagged-pdf --disable-search-engine-choice-screen --unsafely-disable-devtools-self-xss-warnings --edge-skip-compat-layer-relaunch --disable-infobars --disable-search-engine-choice-screen --disable-sync --enable-unsafe-swiftshader --headless --hide-scrollbars --mute-audio --blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4 --no-sandbox --user-data-dir=/tmp/playwright_chromiumdev_profile-DUw1wP --remote-debugging-pipe --no-startup-window
  - <launched> pid=58
  - [pid=58][err] [58:58:1009/225203.107809:ERROR:third_party/crashpad/crashpad/util/file/filesystem_posix.cc:63] mkdir : No such file or directory (2)
  - [pid=58][err] chrome_crashpad_handler: --database is required
  - [pid=58][err] Try 'chrome_crashpad_handler --help' for more information.
  - [pid=58][err] [58:58:1009/225203.244607:FATAL:chrome/browser/process_singleton_posix.cc:297] Check failed: . socket() failed: Operation not permitted (1)
  - [pid=58] <gracefully close start>
  - [pid=58] <kill>
  - [pid=58] <will force kill>
  - [pid=58] <process did exit: exitCode=null, signal=SIGABRT>
  - [pid=58] starting temporary directories cleanup
  - [pid=58] finished temporary directories cleanup
  - [pid=58] <gracefully close end>

```
# U13 hosted browser measurements

Exact source `12745cbb7785d744e8aa2b13324a38dea6017718`, push run `37349416728`, frontend job `111896188038`, compact artifact `11361283953`. U13's seven browser cases passed. The complete frontend job failed other journeys; these measurements do not turn that job green.

Thirty retained samples after three warmups for each 100k / 500k / 1m Han-character synthetic project, spread across twelve chapters:

- Trusted Chromium beforeinput to the second requestAnimationFrame after input p95: **27.0 / 36.6 / 46.9 ms**. This measures a rendering-opportunity proxy, not physical key-to-display or OS IME latency. Active chapters had 8,334 / 41,667 / 83,334 Han characters, not the whole project loaded into one editor. Observed editor replacements during these samples: zero.
- Browser fetch start through JSON parse for real loopback File/API search p95: **61.8 / 204.1 / 381.0 ms**. Warm samples reported zero updated documents and no model call.
- Recorded suggestions of <=100 ms and <=500 ms respectively passed in this environment. They are not universal machine guarantees.

The actual host was an Ubuntu GitHub Actions runner. Playwright's Desktop Chrome device preset supplied a Windows user-agent string; that is not evidence of Windows execution. Native Windows input methods, physical display latency, screen readers and true OS zoom remain NOT_RUN.

Raw samples and artifact SHA256 are retained under `evidence/browser-u13-12745cbb/`. Filenames, payloads and manifest contain only synthetic data, versions, methodology and timings.

## Optional tool loading improvement awaiting its own hosted check

The next local source separates experimental navigation metadata from the workbench and loads its code only when an enabled workbench is opened. A scoped loading/error boundary preserves the existing editor; explicit retry reloads only the interface, not jobs. Focused tests verify OFF does not import it, captured project props, error containment and retained draft text. A local production build measured App 610.54 kB and optional workbench 384.21 kB (minified). The App >500 kB warning remains; this is a bundle measurement, not a cold-start latency claim.

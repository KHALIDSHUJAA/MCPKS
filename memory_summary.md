## User Profile

The user works on Windows with PowerShell and uses Codex as a hands-on implementation agent. Their recent work spans Arabic RTL ERP systems plus adjacent assistant/debugging tooling: KS CMR assistant backend and renderer behavior, a production-style multi-agent AI debugging monorepo, a Django CRM migration, an Excel/VBA Smart School ERP, and an Electron desktop ERP. They repeatedly push for concrete outcomes over discussion: code changes should be wired into the real request path, login/restore behavior should be actually verified, and requested deliverables like runnable systems, `.xlsm`, or `.exe` artifacts should be produced rather than described.

They care strongly about preserving existing product identity during migrations or refactors. When a system already has a dark RTL layout, visual shell, or established flow, they want the architecture improved without redesign drift. Their UI feedback is usually narrow and exact: logo size, animation feel, preview-first printing, assistant speech behavior, button flow, exact phrasing style, and similar scoped adjustments.

Their steering is detail-heavy and operational. Exact cwd paths, error strings, and user-facing behavior constraints should be treated as authoritative. They also care about keeping business meaning intact during technical changes: historical data should not silently change semantics, and assistant/chat features should match real Iraqi usage rather than rigid textbook phrasing.

## User preferences

- When the user asks for implementation, default to making the change, not stopping at explanation or planning.
- When the user asks for a full system and says things like `Do NOT skip any part`, default to end-to-end delivery rather than partial scaffolding.
- When migrating or refactoring an existing product, preserve the current visual identity by default; do not redesign unless the user explicitly asks for it.
- When a request is framed as analysis plus conversion, map the real screens, routes, models, and shell first so the migration mirrors the original product.
- When a system is supposed to use skills automatically, treat auto-detection as the default UX if the user says `No manual selection required`; keep manual selection secondary unless they ask otherwise.
- If the user still wants manual skill selection available but says auto skills should override it, preserve that priority model instead of flattening both into equal options.
- For Arabic assistant/chat work, prefer dialect-first intent handling over rigid keyword matching.
- For KS CMR assistant replies, prefer short, human, colloquial Iraqi phrasing like `هسه عندك ...` with a useful follow-up question when appropriate.
- For conversational assistant features, preserve context across messy input, shorthand, typos, and follow-ups like `وغيرهم؟` instead of treating each message as isolated.
- When KS CMR assistant speech output sounds wrong and the user says it is `not Arabic / not Iraqi dialect` or asks `امسح النطق بصوت`, prefer disabling spoken output instead of continuing to tune built-in browser TTS.
- For KS CMR voice input UX, keep the requested one-button flow: `اريد تضيف زر يكتب ما انطقه اني ونفس الزر اضغطه يرسله بالمحادثه` means dictate into the input first, then send with the same control rather than splitting record/send into separate buttons.
- For print features, keep the flow preview-first; the user explicitly wanted `Preview + زر طباعة` and no direct auto-printing.
- For print intent detection, support colloquial Iraqi phrasing such as `اطبع`, `طلع`, `سود`, and `جيب فاتورة`, not only formal wording.
- When the user asks for auditability around generated documents, log who requested the print, the document type, and the customer.
- When business behavior could drift during migration, preserve historical meaning rather than relying on mutable global settings.
- For desktop-app requests, assume the user wants a real Windows desktop architecture with packaging, not a shallow web wrapper.
- For desktop auth/storage flows, keep browser-style token storage out of renderer code and prefer desktop-safe patterns.
- For UI adjustments, keep edits surgical; the user tends to want exact tweaks to size, motion, glow, icons, and placement rather than broad redesign.
- When the user gives an exact runtime error string, debug the underlying cause directly instead of theorizing from surface symptoms.
- When the user expects a runnable implementation, include build/run validation and smoke tests instead of stopping at code generation.
- When login, RBAC, or activation behavior is part of the task, verify the actual startup and state-transition behavior before calling the work done.
- When the user asks to return an app to an activation screen, clear only local activation/session state unless they explicitly ask to remove data.
- When the user asks for a rename or final artifact, apply the rename globally across runtime/config/packaging and then produce the deliverable.

## General Tips

- Environment repeatedly seen here: Windows, PowerShell, local paths plus mapped drives like `N:\` and `Z:\`.
- Preserve cwd boundaries aggressively. Similar ERP tasks exist in different repos and should not be merged mentally.
- In this environment, freshly created nested Windows repo folders can hit `windows sandbox: setup refresh failed with status exit code: 1`; running from the parent directory and using absolute paths can be the more reliable pattern.
- PowerShell file writes can introduce UTF-8 BOMs that break JSON/Vite/PostCSS parsing; if you see `Unexpected token '﻿'`, check for BOM before chasing deeper config issues.
- In `N:\KS CMR SYSTME`, renderer assistant changes may need behavior-based validation because `npm run typecheck:web` already had unrelated TypeScript failures elsewhere in the repo.
- For Arabic DOCX extraction in this environment, `python-docx` plus `sys.stdout.reconfigure(encoding='utf-8')` avoided Windows console `UnicodeEncodeError`.
- For Electron/Vite config rewrites on Windows, watch for BOM issues. UTF-8 without BOM mattered for `package.json` and related config files.
- Plain `node` verification can be misleading for Electron-native SQLite modules like `better-sqlite3`; prefer Electron-target or build-time validation when ABI mismatch is possible.
- For Excel/VBA startup reliability, `Workbook_Open` alone may be insufficient; `Workbook_Activate` and `Auto_Open` can be necessary backup hooks.
- Keep partial implementations labeled as partial. The KS CMR print assistant service exists, but the captured evidence does not show full controller/router/frontend wiring yet.

## What's in Memory

### Z:\chating ai\ai-debug-system

#### 2026-05-08

- Multi-agent AI debug system with auto-skills, orchestration, and dashboard validation: z:\chating ai\ai-debug-system, auto-skills, full-debug, system-analyzer, fix-engineer, judge-agent, debug-orchestrator, /api/auto-skills, /api/full-debug, qualityScore: 100
  - desc: Covers the production-style monorepo at `cwd=Z:\chating ai\ai-debug-system`: backend analyzer/fixer/judge orchestration, stack/issue-driven auto-skill activation, ZIP/GitHub/inline ingestion, SSE job updates, and the build/smoke-test work that made the system runnable. Search this first for follow-up work on the AI debug platform, agent flow, auto-skills behavior, or repo validation.
  - learnings: The validated command/checkpoint is `npm run build`, and the strongest run proof was `GET /api/health` plus `POST /api/auto-skills` and `POST /api/full-debug` after the fixer learned to rewrite `items.push(1)` to `setItems([...items, 1])`. In this environment, nested `workdir` use could fail with sandbox refresh errors, so parent-dir execution plus absolute paths was the practical workaround.

### N:\KS CMR SYSTME

#### 2026-05-07

- KS CMR renderer AI assistant voice disablement and one-button dictation/send flow: speechSynthesis, SpeechSynthesisUtterance, arabicTts.ts, ENABLE_SPEECH_OUTPUT, StandaloneAiChat, AiChatModal, fillInputFromTranscript, handleVoiceButtonClick
  - desc: Covers the Electron/React assistant UI at `cwd=N:\KS CMR SYSTME`: removing Haji's spoken output after the Arabic/Iraqi voice was rejected, and changing the voice control so the same button dictates into the input, sends existing text, or stops recording. Search this first for `StandaloneAiChat.tsx` / `AiChatModal.tsx` behavior, browser speech API work, or the combined voice-button workflow.
  - learnings: The accepted state from this rollout is text-first interaction with speech output disabled via `ENABLE_SPEECH_OUTPUT = false` in both assistant surfaces. Dictation now fills the input through `fillInputFromTranscript(...)`, and `handleVoiceButtonClick()` owns the `Mic` / `Send` / `Stop` behavior. `npm run typecheck:web` was not a clean verifier because of unrelated pre-existing TS errors elsewhere in the repo.

#### 2026-05-01

- KS CMR Iraqi-dialect assistant understanding and preview-first print workflow: Iraqi dialect, iraqi-language-understanding.ts, iraqi-chat-engine.ts, print-assistant.service.ts, /ai/chat, Preview + زر طباعة, AI_PRINT_PREVIEW_REQUESTED
  - desc: Covers the KS CMR assistant backend at `cwd=N:\KS CMR SYSTME`: Iraqi-language understanding before analysis/SQL, short human-style financial responses, follow-up context handling, and the partially integrated smart print assistant for statements, invoices, last transactions, and full reports. Search this first for assistant behavior, dialect handling, or AI-driven document preview work in KS CMR.
  - learnings: The chat path is the validated part: `/ai/chat` now goes through `iraqi-language-understanding.ts`, uses per-user context keyed by `userId`, and was verified by `npm run typecheck:server`, `npm run build:server`, and direct phrase checks like `وغيرهم؟ -> Follow-up`. The print assistant is not complete end-to-end yet; the service exists, but request-path wiring and `PrintPreviewModal.tsx` still need completion.

### N:\crm-update20-4\crm

#### 2026-04-21

- Django CRM migration analysis and currency-safe Node/PostgreSQL conversion: Django, crm/urls.py, templates/base.html, currency per record, currencyUtils.js, Debt.currency, Payment.currency
  - desc: Covers the CRM checkout at `cwd=N:\crm-update20-4\crm`: extracting the existing Django RTL dark/gold shell and module map before migration, then hardening the new Node/Flutter/React stack so debts and payments keep historical currency per record. Search this first for migration planning, route/theme mapping, or money-field semantics in this CRM.
  - learnings: `templates/base.html` is the canonical shell, most styling lives inline in templates, and the strongest validation was the API smoke test proving `debtA_currency=IQD`, `debtA_payment_currency=USD`, `debtB_currency=USD` after a company-currency change. Also note the environment-specific failure: `'vite' is not recognized as an internal or external command`.

### Older Memory Topics

#### Z:\Smart School ERP

- Smart School ERP workbook build, RBAC, and login gate hardening: SmartSchoolERP_Blueprint.docx, cfg_Users, frm_Login, frm_UserManager, Workbook_Open, Workbook_Activate, Auto_Open, GetTargetWorkbook
  - desc: Covers the Excel/VBA Smart School ERP at `cwd=Z:\Smart School ERP`: blueprint-to-workbook generation, in-workbook user management, normalized RBAC keys, strict pre-login lock, and the fixes that made login show first and sheets reveal correctly after auth. Use this for workbook rebuilds, VBA security flow, or Arabic RTL school-ERP Excel behavior.

#### n:\antigravity\erpv2backup

- KS ERP DESKTOP Electron build, restore fixes, branding, and installer: solar_erp_2.jsx, Electron, Vite, better-sqlite3, backup:local:restore, KS ERP DESKTOP, release/KS ERP DESKTOP-Setup-1.0.0.exe
  - desc: Covers the full desktop ERP conversion in `cwd=n:\antigravity\erpv2backup`: rebuilding a single-file UI into a real Electron/React/Vite/TypeScript/SQLite app, preserving the dark RTL UI, fixing `SqliteError: FOREIGN KEY constraint failed` in restore, resetting activation via local state only, globally renaming to `KS ERP DESKTOP`, and producing the NSIS installer.

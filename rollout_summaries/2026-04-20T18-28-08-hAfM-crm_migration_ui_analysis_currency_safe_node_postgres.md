thread_id: 019dac26-5c89-79a0-97e3-5513a959feda
updated_at: 2026-04-21T12:54:29+00:00
rollout_path: C:\Users\KHALID SHUJAA\.codex\sessions\2026\04\20\rollout-2026-04-20T21-28-08-019dac26-5c89-79a0-97e3-5513a959feda.jsonl
cwd: \\?\N:\crm-update20-4\crm
git_branch: main

# Analyzed the Django CRM for migration to React / Flutter Web + Node.js + PostgreSQL, then implemented a currency-safe backend/frontend migration path.

Rollout context: The user asked in Arabic to analyze the app’s templates, styling, layout, and functions, and convert it to React / Flutter Web (UI), Node.js (server), and PostgreSQL while preserving section order, style, positions, colors, and content layout. The project root was `N:\crm-update20-4\crm`.

## Task 1: Analyze the existing Django app and map its UI / backend surface
Outcome: success

Preference signals:
- The user explicitly asked to preserve "ترتيب وستايل ومواقع كل قسم ومحتوياتهم ولون" -> in similar migrations, the default should be to extract the current UI structure and styling first rather than redesigning.
- The user’s request framed the work as analysis + conversion, not just code changes -> future agents should build a screen/function map before editing.

Key steps:
- The app was identified as a Django 5.2.3 CRM with Bootstrap RTL templates, Font Awesome, Chart.js, and Arabic UI assets.
- `crm/urls.py`, `crm/models.py`, and `crm/views.py` were inspected and the major surfaces were enumerated:
  - customers, debts, payments, invoices, reports, backup, settings, WhatsApp, auth.
- `templates/base.html` and `templates/auth/login.html` were read to extract the shared layout:
  - dark/gold theme, RTL layout, left sidebar, top navbar, watermark, developer footer.
- The template scan showed that most styling lived inline in templates rather than in standalone CSS files, which matters for migration fidelity.

Reusable knowledge:
- `templates/base.html` is the canonical source for the app shell: navbar, sidebar, watermark, developer footer, Bootstrap/Chart.js includes.
- The app’s core routes are concentrated in `crm/urls.py`; the main functional modules are customers, debts, payments, invoices, reports, backup, and WhatsApp.
- The Django backend already separates company settings through a context processor, which made the theme and company name available globally in templates.

References:
- [1] `crm/urls.py` includes routes such as `dashboard`, `customers/`, `debts/`, `payments/`, `invoices/`, `reports/`, `backup/`, and WhatsApp endpoints.
- [2] `templates/base.html` defines RTL shell, dark gradient background, gold accents, sidebar navigation, and Chart.js/Bootstrap includes.
- [3] `crm/views.py` contains 20+ handlers including customer CRUD, debt/payment flows, invoice PDF, reports, backup import/export, currency/logo settings, and WhatsApp messaging.

## Task 2: Migrate currency handling to be record-level instead of global-only
Outcome: success

Preference signals:
- The user wanted to preserve content/layout while converting technologies, which in practice meant business behavior had to remain consistent even as the stack changed.
- The migration surfaced a meaningful product rule: changing the company currency should not retroactively rewrite old records -> future work in this app should default to preserving historical currency per record.

Key steps:
- A new helper `backend-node/src/controllers/helpers/currencyUtils.js` was added to normalize currency and ensure `debts.currency` and `payments.currency` columns exist.
- Backend controllers were updated so that:
  - debt creation stores currency on the debt row,
  - payment creation stores currency on the payment row,
  - list/detail endpoints return currency fields,
  - invoices/reports/backup export/import carry currency through.
- Prisma schema and SQL schema were updated to include `currency` on both `Debt` and `Payment`.
- Frontend formatting was updated so amounts render with the record’s currency instead of always using `$`.

Failures and how to do differently:
- `flutter analyze` completed with only `info` warnings, but the React build failed because `vite` was not installed/available in that environment (`'vite' is not recognized as an internal or external command`).
- The first analysis run hit sandbox limits/timeouts; switching to escalated syntax checks (`node --check`) worked.
- One backend file briefly had a duplicated `payments:` line after patching; it was corrected immediately.

Reusable knowledge:
- For this migration family, do not rely on a single global currency setting for rendering money values; treat currency as a per-record field and only use company currency as the default at creation time.
- Backend runtime syntax checks on the updated Node controllers succeeded with `node --check` after escalation.
- `flutter analyze` can be used as a front-end sanity check, but in this environment it reported only deprecation/info issues, not blocking failures.

References:
- [1] `backend-node/src/controllers/helpers/currencyUtils.js` provides `ensureDebtPaymentCurrencyColumns()` and `normalizeCurrencyCode()`.
- [2] `debtsController.js` now inserts `currency` when creating debts and returns `currency` in debt payloads.
- [3] `paymentsController.js` now inserts/returns `currency` for payments and includes `debt_currency` in list responses.
- [4] `invoicesController.js`, `reportsController.js`, and `backupController.js` were updated to propagate currency in lists, PDF output, and backups/imports.
- [5] `frontend-flutter-web/lib/core/utils/formatters.dart` now exposes `moneyWithCurrency(...)`.
- [6] Verified API smoke test output showed historical currency preservation: `debtA_currency = IQD`, `debtA_payment_currency = USD`, `debtB_currency = USD` after changing company currency between inserts.

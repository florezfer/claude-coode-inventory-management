# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Factory Inventory Management System Demo — Vue 3 frontend, Python FastAPI backend, in-memory mock data (no database).

> ⚠️ **This repository and any fork you create are PUBLIC.** Do not commit credentials, internal hostnames, or private registry URLs. `client/.npmrc` pins the public npm registry and `client/package-lock.json` is gitignored to prevent locally-configured registries from leaking into commits — leave both in place.

## Critical Tool Usage Rules

### Subagents
Use the Task tool with these specialized subagents for appropriate tasks:

- **vue-expert**: Use for Vue 3 frontend features, UI components, styling, and client-side functionality
  - **MANDATORY RULE: ANY time you need to create or significantly modify a .vue file, you MUST delegate to vue-expert**
- **code-reviewer**: Use after writing significant code to review quality and best practices
- **security-auditor**: Use for security review of changes
- **Explore**: Use for understanding codebase structure or searching for patterns
- **general-purpose**: Use for complex multi-step tasks or when other agents don't fit

### Skills
- **backend-api-test** skill: Use when writing or modifying tests in `tests/backend`

### MCP Tools
- **ALWAYS use GitHub MCP tools** (`mcp__github__*`) for ALL GitHub operations
  - Exception: Local branches only — use `git checkout -b` instead of `mcp__github__create_branch`
- **ALWAYS use Playwright MCP tools** (`mcp__playwright__*`) for browser testing
  - Test against: `http://localhost:3000` (frontend), `http://localhost:8001` (API)

## Commands

```bash
./scripts/start.sh          # Both servers; installs deps on first run. Blocks — Ctrl+C to quit.
./scripts/stop.sh           # Stop both (reads /tmp/inventory-*.pid)
```

Logs land in `/tmp/inventory-backend.log` and `/tmp/inventory-frontend.log`.

Individually:

```bash
cd server && uv run python main.py    # :8001, docs at /docs
cd client && npm run dev              # :3000
cd client && npm run build            # production build
```

### Tests

There is no `pyproject.toml` in `tests/`, so pytest must be run against the server project.
Plain `uv run pytest` from `tests/` fails with "Failed to spawn: pytest".

```bash
cd tests && uv run --project ../server pytest                                  # all 97 tests
cd tests && uv run --project ../server pytest backend/test_inventory.py        # one file
cd tests && uv run --project ../server pytest backend/test_dashboard.py::TestDashboardEndpoints
cd tests && uv run --project ../server pytest -k low_stock                     # one test by name
```

`tests/pytest.ini` supplies `-v --strict-markers --tb=short` and sets `testpaths = backend`.
`tests/backend/conftest.py` puts `server/` on `sys.path` and exposes a `client` fixture (FastAPI `TestClient`).

There is **no linter, formatter, type checker, or frontend test runner** configured in this repo, despite what `/test` implies.

## Architecture

### Data flow
`server/data/*.json` → loaded once at import by `server/mock_data.py` into module-level lists → filtered in-process by `server/main.py` → validated by Pydantic `response_model` → `client/src/api.js` (axios) → view refs → computed properties → template.

Data is read-only and never persisted. Editing a JSON file requires a server restart.

### Filter system
Four global filters — Time Period, Location (`warehouse`), Category, Order Status.

`client/src/composables/useFilters.js` declares its four refs **at module scope, outside the exported function**, so every component that calls `useFilters()` shares one singleton state. Views do not receive filters as props; they `watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus])` and re-fetch. `getCurrentFilters()` renames `selectedLocation` → `warehouse` and `selectedPeriod` → `month` for the API.

Server side, `main.py` has two helpers:
- `apply_filters(items, warehouse, category, status)` — exact match on `warehouse`, case-insensitive on `category`/`status`, skips any value of `'all'`.
- `filter_by_month(items, month)` — matches `YYYY-MM` substrings, or expands `Q1-2025` style keys via `QUARTER_MAP`.

`filter_by_month` reads **only the `order_date` field**, so it applies to orders and dashboard summary. Inventory has no time dimension and ignores the period filter.

### i18n and currency
`useI18n.js` is also a module-scope singleton, persisting locale to `localStorage['app-locale']`. Currency is **derived from locale, not chosen separately** — `ja` ⇒ JPY, everything else ⇒ USD. `client/src/utils/currency.js` converts with a hardcoded `USD_TO_JPY = 150`; underlying JSON values are always USD.

Beyond UI strings, `useI18n` also translates data values at render time: `translateProductName`, `translateCustomerName`, `translateWarehouse` (the last maps city names and rewrites the `Warehouse X-##` prefix). Adding products, customers, or warehouses means adding entries to `client/src/locales/ja.js` or they render untranslated.

### Routing
`client/src/main.js` registers seven routes: `/`, `/inventory`, `/orders`, `/demand`, `/restocking`, `/spending`, `/reports`. Navigation is driven by the `navItems` array at the top of `App.vue` (route, `nav.*` label key, SVG icon paths) — adding a tab means one entry there, a route in `main.js`, and a `nav.*` key in each locale.

### Layout shell
`App.vue` is a dark left sidebar plus a content column; there is no top nav.

- **Sidebar** (`#0f172a`, 248px): brand, `navItems`, then a footer holding `ProfileMenu` and a collapse toggle. On desktop it collapses to a 72px icon rail; the choice persists in `localStorage['app-sidebar-collapsed']`. At ≤900px it becomes an off-canvas drawer opened from a hamburger in `.mobile-header`, closed by Escape, backdrop tap, or navigating.
- **Top bar** (sticky): `FilterBar` plus `LanguageSwitcher`. `FilterBar` no longer owns any sticky/background styling. The language switcher is rendered twice — in the top bar on desktop (`.desktop-language`) and in the mobile header (`.mobile-language`) — with CSS showing one.
- `ProfileMenu` takes a `collapsed` prop. It opens **upward** from the footer (to the right of the rail when collapsed), since the sidebar sits at the bottom-left.
- Shell tokens are CSS variables on `:root` in `App.vue` (`--sidebar-width`, `--sidebar-bg`, `--accent`, …). Collapsing just redefines `--sidebar-width` on `.app`, which moves both the sidebar and the content margin. Colors inside the views are still hardcoded hex, not tokens.
- Stacking: sidebar `z-index: 200`, top bar `100`, modals `2000`. Keep new overlays above 200.
- The shared `.card`, `.stat-card`, `table` and `.badge` classes in `App.vue`'s unscoped `<style>` restyle every view at once; the views carry their own scoped overrides on top.
- `Dashboard.vue`'s KPI row uses a container query: five cards need 1164px to sit in one row, so below that it lays out 3 + 2 rather than leaving an orphan.

## Restocking

`GET /api/restocking/recommendations?budget=N` returns a budget-constrained restock plan; `POST /api/restocking-orders` submits one; `GET /api/restocking-orders` lists them newest first.

- **The forecast joins to inventory by SKU.** `build_restocking_plan()` looks up each `demand_forecasts` SKU in `inventory_items` for cost, category and stock on hand, so `server/data/demand_forecasts.json` must only ever reference real inventory SKUs. `test_demand_forecast_skus_exist_in_inventory` guards this — the two files used to have near-disjoint SKU namespaces, which silently collapsed the Demand tab to one row under any filter.
- **Greedy allocation**: items with `forecasted_demand > quantity_on_hand` are ranked by shortfall descending (SKU as tiebreak) and funded in order until the budget runs out. The last affordable item may be partially funded, flagged `fully_funded: false`.
- **Lead time is per category** (`CATEGORY_LEAD_TIME_DAYS`), and an order takes the **longest** lead time across its lines, not the shortest.
- Order lines are priced from inventory, never from the client payload. Unknown SKU → 404; empty `items` or non-positive quantity → 422.

Like purchase orders, submitted orders live only in the in-memory `restocking_orders` list and are reset per test by an autouse fixture in `conftest.py`.

## Purchase orders

`POST /api/purchase-orders` raises one against a backlog item; `GET /api/purchase-orders/{backlog_item_id}` fetches it back. Rules enforced by the routes:

- **One purchase order per backlog item** — a second attempt returns 409. This invariant is what makes the `has_purchase_order` flag on `GET /api/backlog` meaningful.
- Unknown `backlog_item_id` → 404. Malformed `expected_delivery_date` (anything but `YYYY-MM-DD`) → 400. Non-positive quantity, negative cost or empty supplier → 422 from Pydantic `Field` constraints.
- The server assigns `id` (`PO-0001`, `PO-0002`, …), `status` (`Pending`) and `created_date`. Clients never supply them.

Purchase orders are appended to the in-memory `purchase_orders` list and are **not written back to `server/data/purchase_orders.json`** — they vanish on restart, consistent with the rest of the data layer. Because that list is module-level, `tests/backend/conftest.py` has an autouse `reset_purchase_orders` fixture that snapshots and restores it around every test; without it, a created purchase order would leak into the backlog tests.

## Unimplemented endpoints

`client/src/api.js` still calls four endpoints the backend does not define. These 404 at runtime:

| Client method | Called path | Backend route |
|---|---|---|
| `getTasks` / `createTask` / `deleteTask` / `toggleTask` | `/api/tasks` | none |

`TasksModal.vue` (621 lines) is wired into `App.vue` and calls them.

The two purchase-order methods in `api.js` now have routes, but nothing calls them yet. `Dashboard.vue` already renders Create PO / View PO buttons, `openPOModal` handlers and a `<PurchaseOrderModal>` tag — but **`components/PurchaseOrderModal.vue` does not exist** (Vue logs `Failed to resolve component: PurchaseOrderModal` on every Dashboard load). Creating that modal, wired to `createPurchaseOrder` / `getPurchaseOrderByBacklogItem` and emitting `po-created`, is the remaining frontend work.

## Known inconsistencies

Verify against the code rather than trusting these docs:

1. Two divergent MCP configs exist: `.mcp.json` (playwright pinned `0.0.37`) and `.claude/mcp-config.json` (playwright `@latest`). `.mcp.json` is the one Claude Code reads.
2. `client/src/views/Backlog.vue` is orphaned — absent from the router and imported nowhere. Backlog is surfaced through `BacklogDetailModal.vue` from `Dashboard.vue` instead.
3. There is still **no `test_orders.py`**, so `/api/orders` and its four-way filtering — the most filter-sensitive surface in the API — is uncovered. A `sample_order` fixture sits unused in `conftest.py`.
4. `client/src/views/Reports.vue` bypasses `api.js`, importing axios directly and hardcoding `http://localhost:8001` twice.
5. Two currency conventions coexist: `formatCurrency()` (Dashboard, Spending, Restocking) converts USD→JPY, while the `currencySymbol` pattern (Orders, Inventory) swaps the symbol **without** converting the number.
6. `components/PurchaseOrderModal.vue` is imported by name in `Dashboard.vue`'s template but missing — see Purchase orders above.
7. `server/pyproject.toml` requires Python `>=3.11`; `uv` resolves to whatever is newest locally.

## Key files

- `server/main.py` (538 lines) — every route, Pydantic model, and filter helper
- `client/src/views/Dashboard.vue` (1271 lines) — largest file; KPIs, charts, modals
- `client/src/api.js` — the only place axios is called
- `client/src/App.vue` — the app shell (sidebar, top bar) and the shared global styles; there is no separate stylesheet

## Conventions

- **v-for keys**: use a domain id (`sku`, `id`, `month`), never the array index
- **Dates**: validate with `isNaN(date.getTime())` before `.getMonth()`
- **Pydantic**: update the model whenever the shape of a JSON file changes
- **Revenue goals**: $800K per month, $9.6M YTD across all months
- **Charts**: hand-written SVG with CSS Grid layout — no charting library
- **Colors**: slate/gray (`#0f172a`, `#64748b`, `#e2e8f0`); status green/blue/yellow/red
- **No emojis in UI**

Subdirectory `CLAUDE.md` files in `server/` and `client/` cover framework-level practice (FastAPI patterns, Composition API patterns) in depth.

# API Tests

Test suite for the Factory Inventory Management System backend APIs.

## Test Structure

```
tests/
├── pytest.ini          # Pytest configuration
├── backend/            # Backend API tests
│   ├── conftest.py     # Test fixtures and configuration
│   ├── test_inventory.py      # Inventory endpoint tests (10 tests)
│   ├── test_dashboard.py      # Dashboard endpoint tests (13 tests)
│   ├── test_misc_endpoints.py # Demand, backlog, spending, root (18 tests)
│   ├── test_purchase_orders.py # Purchase order endpoint tests (24 tests)
│   └── test_restocking.py     # Restocking endpoint tests (32 tests)
└── README.md           # This file
```

## Running Tests

There is no `pyproject.toml` in `tests/`, so pytest has to be run against the
server project with `--project ../server`. A plain `uv run pytest` from this
directory fails with `Failed to spawn: pytest`.

### Run all tests
```bash
cd tests
uv run --project ../server pytest
```

### Run specific test file
```bash
cd tests
uv run --project ../server pytest backend/test_inventory.py
```

### Run specific test class
```bash
cd tests
uv run --project ../server pytest backend/test_inventory.py::TestInventoryEndpoints
```

### Run specific test
```bash
cd tests
uv run --project ../server pytest backend/test_inventory.py::TestInventoryEndpoints::test_get_all_inventory
```

### Run tests matching a name
```bash
cd tests
uv run --project ../server pytest -k low_stock
```

### Run with coverage (pytest-cov is already a dev dependency)
```bash
cd tests
uv run --project ../server pytest --cov=../server --cov-report=html
```

`pytest.ini` already supplies `-v --strict-markers --tb=short`, so there is no
need to pass `-v` yourself.

## Test Coverage

**Total: 97 tests.** Statement coverage of `server/` is roughly 65%
(`main.py` 77%, `mock_data.py` 100%).

### Inventory Endpoints (10 tests) — `TestInventoryEndpoints`
- ✓ Get all inventory items
- ✓ Filter by warehouse
- ✓ Filter by category (including Power Supplies)
- ✓ Filter by warehouse and category together
- ✓ Handle the `all` sentinel value
- ✓ Get specific item by ID
- ✓ Handle non-existent items (404)
- ✓ Validate field structure and data types

### Dashboard Endpoints (13 tests) — `TestDashboardEndpoints`
- ✓ Get dashboard summary
- ✓ Validate data types and non-negative values
- ✓ Filter by warehouse, category, status, month
- ✓ Multiple and all-filter combinations
- ✓ Validate calculation accuracy:
  - Pending orders calculation
  - Low stock items calculation
  - Total inventory value calculation

### Miscellaneous Endpoints (18 tests) — `test_misc_endpoints.py`
- **Demand Forecasts (5 tests)** — `TestDemandEndpoints`
  - ✓ Get demand forecasts
  - ✓ Validate trend values
  - ✓ Validate non-negative values
  - ✓ Stable items have small changes
  - ✓ Forecast includes newer items

- **Backlog Items (4 tests)** — `TestBacklogEndpoints`
  - ✓ Get backlog items
  - ✓ Validate priority values
  - ✓ Validate quantity logic
  - ✓ Validate days delayed

- **Spending Data (6 tests)** — `TestSpendingEndpoints`
  - ✓ Get spending summary
  - ✓ Get monthly spending
  - ✓ Monthly spending covers all cost categories
  - ✓ Monthly spending varies across months
  - ✓ Get category spending
  - ✓ Get recent transactions

- **Root Endpoint (2 tests)** — `TestRootEndpoint`
  - ✓ API info endpoint
  - ✓ Validate response structure

### Purchase Orders (24 tests) — `test_purchase_orders.py`
- **Creation (15 tests)** — `TestCreatePurchaseOrder`
  - ✓ 201 with the created resource, server-assigned sequential id
  - ✓ Defaults to `Pending`, stamps an ISO 8601 `created_date`
  - ✓ Optional `notes` omitted
  - ✓ 404 for an unknown backlog item
  - ✓ 409 when the backlog item already has a purchase order
  - ✓ 400 for a malformed or impossible `expected_delivery_date`
  - ✓ 422 for non-positive quantity, negative cost, empty supplier, missing id
- **Retrieval (6 tests)** — `TestGetPurchaseOrderByBacklogItem`
  - ✓ Round-trips a created purchase order
  - ✓ Full field set and field types
  - ✓ 404 when none exists for that backlog item
  - ✓ One backlog item's purchase order never leaks into another's
- **Backlog integration (3 tests)** — `TestBacklogPurchaseOrderFlag`
  - ✓ `has_purchase_order` is false before any are raised
  - ✓ Flips on creation, for that item only
  - ✓ Tracks several purchase orders independently

### Restocking (32 tests) — `test_restocking.py`
- **Recommendations (15 tests)** — `TestRestockingRecommendations`
  - ✓ Zero budget yields an empty plan; negative and missing budget are 422
  - ✓ Greedy order: largest shortfall funded first
  - ✓ Full-coverage budget ($80,205.20) funds all six short items
  - ✓ Last affordable item is partially funded, flagged `fully_funded: false`
  - ✓ Budget is never exceeded; `total_cost + remaining_budget == budget`
  - ✓ Well-stocked items are never recommended
  - ✓ Plan is deterministic for a given budget
- **Submission (12 tests)** — `TestCreateRestockingOrder`
  - ✓ 201 with a server-assigned `RST-2025-0001`, incrementing
  - ✓ Lines priced from inventory, not from the client
  - ✓ Lead time is the **longest** across ordered categories
  - ✓ `expected_delivery` = `submitted_date` + lead time
  - ✓ Unknown SKU 404; empty items and non-positive quantity 422
  - ✓ A rejected order leaves no trace
- **Retrieval (4 tests)** — `TestGetRestockingOrders`
  - ✓ Empty initially, newest first, full field set

### Known gaps

- **No tests for the orders endpoints.** `GET /api/orders` and
  `GET /api/orders/{order_id}` — including their warehouse, category, status
  and month/quarter filtering — are currently uncovered.
- `GET /api/reports/quarterly` and `GET /api/reports/monthly-trends` are
  uncovered.

## Test Features

- **FastAPI TestClient**: Uses FastAPI's built-in test client for fast, isolated testing
- **Fixtures**: Reusable test fixtures in `conftest.py` — `client`,
  `sample_inventory_item`, `sample_order`
- **Comprehensive Validation**: Tests data structure, types, calculations, and business logic
- **Filter Testing**: Validates filter combinations and edge cases
- **Error Handling**: Tests 404 responses and edge cases

`conftest.py` puts `server/` on `sys.path` before importing `main`, which is why
the tests can run from this directory without the server package being installed.

## Dependencies

Tests require the following packages, declared under `[tool.uv] dev-dependencies`
in `server/pyproject.toml` and installed with `uv sync`:
- pytest >= 8.0.0
- pytest-asyncio >= 0.23.0
- httpx >= 0.27.0
- pytest-cov >= 4.1.0 (for coverage reports)

## Adding New Tests

1. Create test file in `tests/backend/` following naming convention `test_*.py`
2. Take the `client` fixture as a test argument (pytest injects it from `conftest.py`)
3. Create test class (optional but recommended for organization)
4. Write test functions starting with `test_`
5. Run tests to verify

Example:
```python
class TestNewEndpoint:
    def test_new_feature(self, client):
        response = client.get("/api/new-endpoint")
        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data
```

## CI/CD Integration

To integrate with CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run API Tests
  run: |
    cd tests
    uv run --project ../server pytest
```

## Notes

- All tests use in-memory mock data (no database required)
- Tests are independent and can run in any order
- FastAPI TestClient handles app lifecycle automatically
- The suite runs in well under a second

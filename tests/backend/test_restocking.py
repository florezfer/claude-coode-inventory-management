"""
Tests for the restocking endpoints.

GET  /api/restocking/recommendations?budget=  - budget-constrained restock plan
POST /api/restocking-orders                   - submit a restocking order
GET  /api/restocking-orders                   - list submitted orders
"""
from datetime import datetime

# Items the seeded forecast expects to run short, in greedy order.
# (sku, shortfall, unit_cost, line cost at full coverage)
EXPECTED_SHORTFALLS = [
    ("PRS-203", 550, 12.75, 7012.50),
    ("PCB-001", 450, 24.99, 11245.50),
    ("PSU-506", 280, 29.99, 8397.20),
    ("LED-406", 200, 32.75, 6550.00),
    ("GYR-207", 120, 95.00, 11400.00),
    ("SRV-301", 80, 445.00, 35600.00),
]

FULL_COVERAGE_COST = 80205.20


def plan(client, budget):
    """Fetch a restocking plan for a budget."""
    response = client.get(f"/api/restocking/recommendations?budget={budget}")
    assert response.status_code == 200
    return response.json()


class TestRestockingRecommendations:
    """Tests for GET /api/restocking/recommendations"""

    def test_zero_budget_recommends_nothing(self, client):
        """A budget of zero is valid and yields an empty plan, not an error."""
        data = plan(client, 0)

        assert data["items"] == []
        assert data["total_cost"] == 0
        assert data["remaining_budget"] == 0

    def test_negative_budget_rejected(self, client):
        """Budget must not be negative."""
        response = client.get("/api/restocking/recommendations?budget=-100")

        assert response.status_code == 422

    def test_budget_is_required(self, client):
        """Omitting the budget is a validation error, not a default."""
        response = client.get("/api/restocking/recommendations")

        assert response.status_code == 422

    def test_small_budget_funds_largest_shortfall_first(self, client):
        """The greedy rule starts with the biggest gap."""
        data = plan(client, 8000)

        assert data["items"][0]["sku"] == "PRS-203"
        assert data["items"][0]["recommended_quantity"] == 550
        assert data["items"][0]["fully_funded"] is True

    def test_items_ordered_by_shortfall_descending(self, client):
        """Recommendations come back largest-shortfall first."""
        data = plan(client, FULL_COVERAGE_COST)

        shortfalls = [item["shortfall"] for item in data["items"]]
        assert shortfalls == sorted(shortfalls, reverse=True)

    def test_full_budget_covers_every_shortfall(self, client):
        """A budget matching full coverage funds all six items completely."""
        data = plan(client, FULL_COVERAGE_COST)

        assert [item["sku"] for item in data["items"]] == [s[0] for s in EXPECTED_SHORTFALLS]
        assert all(item["fully_funded"] for item in data["items"])
        assert data["total_cost"] == FULL_COVERAGE_COST
        assert data["remaining_budget"] == 0

    def test_recommended_quantities_match_shortfalls(self, client):
        """With enough budget each line fills exactly the shortfall."""
        data = plan(client, FULL_COVERAGE_COST)

        for item, (sku, shortfall, unit_cost, line_cost) in zip(data["items"], EXPECTED_SHORTFALLS):
            assert item["sku"] == sku
            assert item["shortfall"] == shortfall
            assert item["recommended_quantity"] == shortfall
            assert item["unit_cost"] == unit_cost
            assert item["line_cost"] == line_cost

    def test_surplus_budget_is_not_overspent(self, client):
        """Beyond full coverage the extra budget is simply left over."""
        data = plan(client, 200000)

        assert data["total_cost"] == FULL_COVERAGE_COST
        assert data["remaining_budget"] == round(200000 - FULL_COVERAGE_COST, 2)

    def test_last_item_can_be_partially_funded(self, client):
        """A budget that runs out mid-item funds it partially."""
        # Covers PRS-203 fully (7012.50) with 2499.00 to spare, which buys
        # 100 of PCB-001's 450 shortfall at 24.99.
        data = plan(client, 9511.50)

        assert len(data["items"]) == 2
        assert data["items"][0]["fully_funded"] is True
        partial = data["items"][1]
        assert partial["sku"] == "PCB-001"
        assert partial["recommended_quantity"] == 100
        assert partial["fully_funded"] is False

    def test_budget_is_never_exceeded(self, client):
        """Total cost stays within budget at a range of budgets."""
        for budget in [500, 7012.50, 9511.50, 25000, 50000, 80205.20]:
            data = plan(client, budget)
            assert data["total_cost"] <= budget
            assert data["remaining_budget"] >= 0

    def test_cost_and_remainder_reconcile(self, client):
        """total_cost + remaining_budget always equals the budget."""
        for budget in [1000, 25000, 60000, 120000]:
            data = plan(client, budget)
            assert abs(data["total_cost"] + data["remaining_budget"] - budget) < 0.01

    def test_line_costs_sum_to_total(self, client):
        """The per-line costs add up to the reported total."""
        data = plan(client, 50000)

        assert abs(sum(i["line_cost"] for i in data["items"]) - data["total_cost"]) < 0.01

    def test_well_stocked_items_never_recommended(self, client):
        """Items whose forecast is below stock on hand are excluded."""
        data = plan(client, 500000)

        recommended = {item["sku"] for item in data["items"]}
        # Stable and decreasing forecast items are all comfortably stocked
        for sku in ["MCU-401", "PRX-204", "DRV-405", "SPR-602", "PSU-502", "STP-304", "MCU-402"]:
            assert sku not in recommended

    def test_recommendations_have_positive_quantities(self, client):
        """A line is never emitted with nothing to buy."""
        data = plan(client, 25000)

        assert len(data["items"]) > 0
        assert all(item["recommended_quantity"] > 0 for item in data["items"])

    def test_recommendation_carries_inventory_context(self, client):
        """Each line includes the inventory fields the UI needs."""
        data = plan(client, 25000)

        item = data["items"][0]
        expected_fields = {
            "sku", "name", "category", "warehouse", "unit_cost", "quantity_on_hand",
            "forecasted_demand", "shortfall", "recommended_quantity", "line_cost", "fully_funded"
        }
        assert expected_fields == set(item.keys())
        assert item["shortfall"] == item["forecasted_demand"] - item["quantity_on_hand"]

    def test_plan_is_deterministic(self, client):
        """The same budget always produces the same plan."""
        assert plan(client, 30000) == plan(client, 30000)


class TestCreateRestockingOrder:
    """Tests for POST /api/restocking-orders"""

    def test_submit_order(self, client):
        """Submitting an order returns 201 and the created order."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"sku": "PRS-203", "quantity": 550}]
        })

        assert response.status_code == 201
        data = response.json()
        assert data["order_number"] == "RST-2025-0001"
        assert data["status"] == "Submitted"
        assert len(data["items"]) == 1

    def test_order_numbers_increment(self, client):
        """Each submitted order gets the next sequential number."""
        first = client.post("/api/restocking-orders", json={"items": [{"sku": "PRS-203", "quantity": 10}]})
        second = client.post("/api/restocking-orders", json={"items": [{"sku": "PCB-001", "quantity": 10}]})

        assert first.json()["order_number"] == "RST-2025-0001"
        assert second.json()["order_number"] == "RST-2025-0002"

    def test_lines_are_priced_from_inventory(self, client):
        """Unit price comes from inventory, not from the client."""
        data = client.post("/api/restocking-orders", json={
            "items": [{"sku": "PRS-203", "quantity": 100}]
        }).json()

        line = data["items"][0]
        assert line["unit_price"] == 12.75
        assert line["name"] == "Pressure Sensor Module"
        assert data["total_value"] == 1275.00

    def test_total_value_sums_all_lines(self, client):
        """total_value covers every line in the order."""
        data = client.post("/api/restocking-orders", json={
            "items": [
                {"sku": "PRS-203", "quantity": 100},   # 100 * 12.75 = 1275.00
                {"sku": "PCB-001", "quantity": 10}     #  10 * 24.99 =  249.90
            ]
        }).json()

        assert data["total_value"] == 1524.90

    def test_lead_time_from_category(self, client):
        """A single-category order uses that category's lead time."""
        data = client.post("/api/restocking-orders", json={
            "items": [{"sku": "PRS-203", "quantity": 10}]
        }).json()

        assert data["lead_time_days"] == 10  # Sensors

    def test_lead_time_is_the_longest_across_categories(self, client):
        """A mixed order waits for its slowest category, not its fastest."""
        data = client.post("/api/restocking-orders", json={
            "items": [
                {"sku": "PRS-203", "quantity": 10},   # Sensors, 10 days
                {"sku": "SRV-301", "quantity": 5}     # Actuators, 28 days
            ]
        }).json()

        assert data["lead_time_days"] == 28

    def test_expected_delivery_follows_lead_time(self, client):
        """expected_delivery is submitted_date plus the lead time."""
        data = client.post("/api/restocking-orders", json={
            "items": [{"sku": "PCB-001", "quantity": 10}]   # Circuit Boards, 21 days
        }).json()

        submitted = datetime.fromisoformat(data["submitted_date"])
        delivery = datetime.fromisoformat(data["expected_delivery"])
        assert (delivery - submitted).days == 21
        assert data["lead_time_days"] == 21

    def test_unknown_sku_rejected(self, client):
        """A SKU that is not in inventory is a 404."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"sku": "NOPE-999", "quantity": 10}]
        })

        assert response.status_code == 404
        assert "NOPE-999" in response.json()["detail"]

    def test_empty_order_rejected(self, client):
        """An order must have at least one line."""
        response = client.post("/api/restocking-orders", json={"items": []})

        assert response.status_code == 422

    def test_zero_quantity_rejected(self, client):
        """Line quantities must be positive."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"sku": "PRS-203", "quantity": 0}]
        })

        assert response.status_code == 422

    def test_negative_quantity_rejected(self, client):
        """Line quantities must be positive."""
        response = client.post("/api/restocking-orders", json={
            "items": [{"sku": "PRS-203", "quantity": -5}]
        })

        assert response.status_code == 422

    def test_rejected_order_is_not_recorded(self, client):
        """A failed submission leaves no trace."""
        client.post("/api/restocking-orders", json={"items": [{"sku": "NOPE-999", "quantity": 1}]})

        assert client.get("/api/restocking-orders").json() == []


class TestGetRestockingOrders:
    """Tests for GET /api/restocking-orders"""

    def test_empty_before_any_submission(self, client):
        """No orders exist on a fresh server."""
        response = client.get("/api/restocking-orders")

        assert response.status_code == 200
        assert response.json() == []

    def test_lists_submitted_orders(self, client):
        """Submitted orders are returned."""
        client.post("/api/restocking-orders", json={"items": [{"sku": "PRS-203", "quantity": 10}]})

        data = client.get("/api/restocking-orders").json()

        assert len(data) == 1
        assert data[0]["order_number"] == "RST-2025-0001"

    def test_newest_order_first(self, client):
        """The list is ordered newest first."""
        client.post("/api/restocking-orders", json={"items": [{"sku": "PRS-203", "quantity": 10}]})
        client.post("/api/restocking-orders", json={"items": [{"sku": "PCB-001", "quantity": 10}]})
        client.post("/api/restocking-orders", json={"items": [{"sku": "GYR-207", "quantity": 10}]})

        numbers = [order["order_number"] for order in client.get("/api/restocking-orders").json()]

        assert numbers == ["RST-2025-0003", "RST-2025-0002", "RST-2025-0001"]

    def test_order_structure(self, client):
        """The response carries the full RestockingOrder shape."""
        client.post("/api/restocking-orders", json={"items": [{"sku": "PRS-203", "quantity": 10}]})

        order = client.get("/api/restocking-orders").json()[0]

        expected_fields = {
            "id", "order_number", "items", "total_value", "status",
            "submitted_date", "expected_delivery", "lead_time_days"
        }
        assert expected_fields == set(order.keys())

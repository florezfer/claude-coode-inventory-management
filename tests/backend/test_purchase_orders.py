"""
Tests for the purchase order endpoints.

POST /api/purchase-orders                      - raise a PO against a backlog item
GET  /api/purchase-orders/{backlog_item_id}    - fetch the PO for a backlog item
"""


def valid_payload(**overrides):
    """Build a valid create-purchase-order body, with optional field overrides."""
    payload = {
        "backlog_item_id": "1",
        "supplier_name": "Pacific Components Ltd",
        "quantity": 350,
        "unit_cost": 12.75,
        "expected_delivery_date": "2025-11-15",
        "notes": "Expedite - blocking ORD-2025-0927"
    }
    payload.update(overrides)
    return payload


class TestCreatePurchaseOrder:
    """Tests for POST /api/purchase-orders"""

    def test_create_purchase_order(self, client):
        """Creating a purchase order returns 201 and the created resource."""
        response = client.post("/api/purchase-orders", json=valid_payload())

        assert response.status_code == 201
        data = response.json()
        assert data["backlog_item_id"] == "1"
        assert data["supplier_name"] == "Pacific Components Ltd"
        assert data["quantity"] == 350
        assert data["unit_cost"] == 12.75
        assert data["expected_delivery_date"] == "2025-11-15"
        assert data["notes"] == "Expedite - blocking ORD-2025-0927"

    def test_create_purchase_order_assigns_id(self, client):
        """The server assigns the id; the client does not supply one."""
        response = client.post("/api/purchase-orders", json=valid_payload())

        assert response.status_code == 201
        assert response.json()["id"] == "PO-0001"

    def test_create_purchase_order_ids_are_sequential(self, client):
        """Successive purchase orders get incrementing ids."""
        first = client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="1"))
        second = client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="2"))
        third = client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="3"))

        assert [r.json()["id"] for r in (first, second, third)] == ["PO-0001", "PO-0002", "PO-0003"]

    def test_create_purchase_order_defaults_to_pending(self, client):
        """A new purchase order starts in Pending status."""
        response = client.post("/api/purchase-orders", json=valid_payload())

        assert response.json()["status"] == "Pending"

    def test_create_purchase_order_sets_created_date(self, client):
        """created_date is stamped by the server in ISO 8601 form."""
        response = client.post("/api/purchase-orders", json=valid_payload())

        created_date = response.json()["created_date"]
        assert isinstance(created_date, str)
        # YYYY-MM-DDTHH:MM:SS
        assert len(created_date) == 19
        assert created_date[4] == "-" and created_date[7] == "-" and created_date[10] == "T"

    def test_create_purchase_order_without_notes(self, client):
        """notes is optional and comes back as null when omitted."""
        payload = valid_payload()
        del payload["notes"]

        response = client.post("/api/purchase-orders", json=payload)

        assert response.status_code == 201
        assert response.json()["notes"] is None

    def test_create_purchase_order_unknown_backlog_item(self, client):
        """Raising a PO against a backlog item that does not exist is a 404."""
        response = client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="9999"))

        assert response.status_code == 404
        assert "9999" in response.json()["detail"]

    def test_create_duplicate_purchase_order_conflicts(self, client):
        """A backlog item can only carry one purchase order."""
        client.post("/api/purchase-orders", json=valid_payload())
        response = client.post("/api/purchase-orders", json=valid_payload())

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert "PO-0001" in detail

    def test_create_purchase_order_rejects_zero_quantity(self, client):
        """quantity must be positive."""
        response = client.post("/api/purchase-orders", json=valid_payload(quantity=0))

        assert response.status_code == 422

    def test_create_purchase_order_rejects_negative_quantity(self, client):
        """quantity must be positive."""
        response = client.post("/api/purchase-orders", json=valid_payload(quantity=-5))

        assert response.status_code == 422

    def test_create_purchase_order_rejects_negative_unit_cost(self, client):
        """unit_cost may be zero but never negative."""
        response = client.post("/api/purchase-orders", json=valid_payload(unit_cost=-0.01))

        assert response.status_code == 422

    def test_create_purchase_order_rejects_empty_supplier(self, client):
        """supplier_name must be non-empty."""
        response = client.post("/api/purchase-orders", json=valid_payload(supplier_name=""))

        assert response.status_code == 422

    def test_create_purchase_order_rejects_bad_date_format(self, client):
        """expected_delivery_date must be YYYY-MM-DD."""
        response = client.post(
            "/api/purchase-orders",
            json=valid_payload(expected_delivery_date="15/11/2025")
        )

        assert response.status_code == 400
        assert "YYYY-MM-DD" in response.json()["detail"]

    def test_create_purchase_order_rejects_impossible_date(self, client):
        """A well-shaped but invalid calendar date is still rejected."""
        response = client.post(
            "/api/purchase-orders",
            json=valid_payload(expected_delivery_date="2025-02-30")
        )

        assert response.status_code == 400

    def test_create_purchase_order_requires_backlog_item_id(self, client):
        """backlog_item_id is mandatory."""
        payload = valid_payload()
        del payload["backlog_item_id"]

        response = client.post("/api/purchase-orders", json=payload)

        assert response.status_code == 422


class TestGetPurchaseOrderByBacklogItem:
    """Tests for GET /api/purchase-orders/{backlog_item_id}"""

    def test_get_purchase_order_after_create(self, client):
        """A created purchase order is retrievable by its backlog item id."""
        created = client.post("/api/purchase-orders", json=valid_payload()).json()

        response = client.get("/api/purchase-orders/1")

        assert response.status_code == 200
        assert response.json() == created

    def test_get_purchase_order_fields(self, client):
        """The response carries the full PurchaseOrder structure."""
        client.post("/api/purchase-orders", json=valid_payload())

        data = client.get("/api/purchase-orders/1").json()

        expected_fields = {
            "id", "backlog_item_id", "supplier_name", "quantity", "unit_cost",
            "expected_delivery_date", "status", "created_date", "notes"
        }
        assert expected_fields == set(data.keys())

    def test_get_purchase_order_field_types(self, client):
        """Numeric fields come back as numbers, not strings."""
        client.post("/api/purchase-orders", json=valid_payload())

        data = client.get("/api/purchase-orders/1").json()

        assert isinstance(data["id"], str)
        assert isinstance(data["quantity"], int)
        assert isinstance(data["unit_cost"], float)
        assert isinstance(data["status"], str)

    def test_get_purchase_order_not_found(self, client):
        """A backlog item with no purchase order returns 404."""
        response = client.get("/api/purchase-orders/1")

        assert response.status_code == 404
        assert "1" in response.json()["detail"]

    def test_get_purchase_order_unknown_backlog_item(self, client):
        """An id that matches no backlog item at all also returns 404."""
        response = client.get("/api/purchase-orders/9999")

        assert response.status_code == 404

    def test_get_purchase_order_isolates_backlog_items(self, client):
        """Fetching one backlog item's PO never returns another's."""
        client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="2"))

        found = client.get("/api/purchase-orders/2")
        missing = client.get("/api/purchase-orders/3")

        assert found.status_code == 200
        assert found.json()["backlog_item_id"] == "2"
        assert missing.status_code == 404


class TestBacklogPurchaseOrderFlag:
    """The has_purchase_order flag on /api/backlog is derived from purchase orders."""

    def test_flag_is_false_before_any_purchase_order(self, client):
        """With no purchase orders raised, every backlog item reads false."""
        backlog = client.get("/api/backlog").json()

        assert len(backlog) > 0
        assert all(item["has_purchase_order"] is False for item in backlog)

    def test_flag_flips_after_purchase_order_created(self, client):
        """Creating a PO flips the flag on that backlog item only."""
        client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="2"))

        backlog = client.get("/api/backlog").json()
        flagged = [item for item in backlog if item["has_purchase_order"]]

        assert len(flagged) == 1
        assert flagged[0]["id"] == "2"

    def test_flag_tracks_multiple_purchase_orders(self, client):
        """Each backlog item's flag is independent."""
        client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="1"))
        client.post("/api/purchase-orders", json=valid_payload(backlog_item_id="3"))

        backlog = client.get("/api/backlog").json()
        flagged = {item["id"] for item in backlog if item["has_purchase_order"]}

        assert flagged == {"1", "3"}


from fastapi.testclient import TestClient
from backend import database
from backend.main import app


def test_get_existing_order(tmp_path, monkeypatch):
    # 1. 使用临时数据库
    monkeypatch.setattr(
        database,
        "DB_PATH",
        tmp_path / "test.db"
    )

    # 2. 准备测试数据
    database.init_db()
    database.seed_order()

    # 3. 模拟 HTTP 请求
    client = TestClient(app)
    response = client.get("/orders/A1001")

    # 4. 验证结果
    assert response.status_code == 200
    assert response.json()["order_id"] == "A1001"


def test_get_nonexistent_order(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database,
        "DB_PATH",
        tmp_path / "test.db"
    )

    database.init_db()

    client = TestClient(app)
    response = client.get("/orders/A9999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Order not found"
    }

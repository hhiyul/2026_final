"""Real API routes with only MongoDB and heavyweight model inference substituted."""
import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import mongomock
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from auth import AuthService, COOKIE_NAME, token_hash


@pytest.fixture
def backend(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MONGO_DETAILS", "mongodb://test.invalid")
    mongo = mongomock.MongoClient()
    monkeypatch.setattr("pymongo.MongoClient", lambda *args, **kwargs: mongo)
    inference = types.ModuleType("model_pt.inference")
    inference.FashionPipeline = object
    inference.Garment = object
    inference.Hit = object
    monkeypatch.setitem(sys.modules, "model_pt.inference", inference)
    spec = importlib.util.spec_from_file_location("wardrobe_test_app", ROOT / "app.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    module.auth.create_indexes()
    module.garments_collection.insert_many([
        {"garment_id": "bob-shirt", "user_id": "bob", "category": "top", "embedding": [0., 1.], "thumbnail_url": "/thumbnails/bob.jpg", "bbox": [0, 0, 1, 1]},
    ])
    Path("thumbnails/alice.jpg").write_bytes(b"alice image")
    Path("thumbnails/bob.jpg").write_bytes(b"bob image")
    module.app.state.test_garments = module.garments_collection
    client = TestClient(module.app)
    yield module, client
    client.close()


def signup(client, user="alice"):
    response = client.post("/users", json={"user_id": user, "password": "password123"})
    if response.status_code == 201 and user.strip() == "alice":
        client.app.state.test_garments.insert_one({"garment_id": "alice-shirt", "user_id": "alice", "category": "top", "embedding": [1., 0.], "thumbnail_url": "/thumbnails/alice.jpg", "bbox": [0, 0, 1, 1]})
    return response


def login(client, user="alice", password="password123"):
    return client.post("/auth/login", json={"user_id": user, "password": password})


def test_signup_validation_duplicate_and_existing_account(backend):
    module, client = backend
    assert signup(client, "  alice  ").status_code == 201
    assert signup(client).status_code == 409
    assert signup(client, "   ").status_code == 422
    assert client.post("/users", json={"user_id": "short", "password": "123"}).status_code == 422
    stored = module.users_collection.find_one({"user_id": "alice"})
    assert stored["password_hash"].startswith("$argon2")
    assert "password" not in stored
    assert login(client, password="incorrect").status_code == 401
    assert login(client, user="missing").status_code == 401
    assert client.get("/auth/me").status_code == 401
    # Existing account records use the same password hash and require no migration.
    module.users_collection.insert_one({"user_id": "legacy", "password_hash": module.auth.passwords.hash("password123")})
    assert login(client, "legacy").status_code == 200


def test_cookie_shared_nodes_rotation_logout_and_expiration(backend):
    module, client = backend
    signup(client)
    response = login(client)
    assert response.status_code == 200
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header and "samesite=lax" in cookie_header
    token = client.cookies.get(COOKIE_NAME)
    session = module.auth.sessions.find_one({"_id": token_hash(token)})
    assert session and token not in str(session)
    assert client.get("/auth/me").json() == {"user_id": "alice"}
    second_node = AuthService(module.users_collection, module.auth.sessions)
    other_app = FastAPI()
    other_app.include_router(second_node.router)
    with TestClient(other_app) as other:
        other.cookies.set(COOKIE_NAME, token)
        assert other.get("/auth/me").status_code == 200
        assert login(client).status_code == 200
        assert other.get("/auth/me").status_code == 401  # token rotation
        other.cookies.clear()
        other.cookies.set(COOKIE_NAME, client.cookies.get(COOKIE_NAME))
        assert client.post("/auth/logout").status_code == 200
        assert other.get("/auth/me").status_code == 401  # shared revocation
    assert client.get("/auth/me").status_code == 401
    login(client)
    module.auth.sessions.update_many({}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}})
    assert client.get("/auth/me").status_code == 401


def test_anonymous_routes_are_protected(backend):
    _, client = backend
    assert client.get("/garments?user_id=alice").status_code == 401
    assert client.post("/recommend", json={"query": "쿨톤", "user_id": "alice"}).status_code == 401
    assert client.post("/garments", files={"file": ("x.jpg", b"image", "image/jpeg")}).status_code == 401
    assert client.post("/analyze", files={"file": ("x.jpg", b"image", "image/jpeg")}).status_code == 401
    assert client.request("DELETE", "/garments/alice-shirt", json={"password": "password123"}).status_code == 401
    assert client.get("/thumbnails/alice.jpg").status_code == 401


def test_authenticated_owner_and_password_deletion(backend):
    module, client = backend
    signup(client); login(client)
    response = client.get("/garments?user_id=bob")
    assert response.status_code == 200
    assert response.json()["user_id"] == "alice"
    assert [item["garment_id"] for item in response.json()["items"]] == ["alice-shirt"]
    assert "embedding" not in response.json()["items"][0]
    assert client.get("/thumbnails/alice.jpg").status_code == 200
    assert client.get("/thumbnails/bob.jpg").status_code == 404
    assert client.get("/thumbnails/alice.jpg").headers["cache-control"] == "no-store"
    assert client.request("DELETE", "/garments/bob-shirt", json={"user_id": "bob", "password": "password123"}).status_code == 404
    assert client.request("DELETE", "/garments/alice-shirt", json={"password": "wrongpass"}).status_code == 403
    assert client.get("/auth/me").status_code == 200  # wrong delete password does not end session
    assert client.request("DELETE", "/garments/alice-shirt", json={"password": "password123"}).status_code == 200
    assert not Path("thumbnails/alice.jpg").exists()
    assert module.garments_collection.find_one({"garment_id": "bob-shirt"})


def test_upload_and_recommend_cannot_impersonate(backend):
    module, client = backend
    signup(client); login(client)
    class Crop:
        def save(self, path, **kwargs):
            Path(path).write_bytes(b"new thumbnail")
    garment = types.SimpleNamespace(category="top", bbox=[0, 0, 1, 1], conf=.9, area_ratio=.5, embedding=np.array([1., 0.]), crop=Crop())
    class Pipeline:
        def analyze(self, *args, **kwargs):
            return [garment]
        def recommend(self, query, embeddings, **kwargs):
            assert all(list(row) == [1., 0.] for row in embeddings)
            return [types.SimpleNamespace(index=0, rank=1, score=.9)]
    module.pipe = Pipeline()
    response = client.post("/garments", data={"user_id": "bob"}, files={"file": ("x.jpg", b"image", "image/jpeg")})
    assert response.status_code == 200
    new_id = response.json()["registered_items"][0]["garment_id"]
    assert module.garments_collection.find_one({"garment_id": new_id})["user_id"] == "alice"
    response = client.post("/recommend", json={"user_id": "bob", "query": "쿨톤", "top_k": 5})
    assert response.status_code == 200
    assert response.json()["results"][0]["garment_id"] == "alice-shirt"


def test_cross_origin_mutation_rejected_and_cors_credentials(backend):
    _, client = backend
    assert client.post("/users", headers={"origin": "https://untrusted.invalid"}, json={"user_id": "alice", "password": "password123"}).status_code == 403
    signup(client); login(client)
    assert client.post("/auth/logout", headers={"origin": "https://untrusted.invalid"}).status_code == 403
    assert client.get("/auth/me").status_code == 200
    response = client.options("/auth/login", headers={"origin": "http://localhost:5173", "access-control-request-method": "POST", "access-control-request-headers": "content-type"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_legacy_anonymous_wardrobe_cannot_be_claimed(backend):
    module, client = backend
    assert signup(client, "bob").status_code == 409
    assert module.users_collection.find_one({"user_id": "bob"}) is None
    assert login(client, "bob").status_code == 401

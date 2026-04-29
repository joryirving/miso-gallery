import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_client(monkeypatch, tmp_path, *, api_keys="agent-key", auth_type="local"):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "sample.png").write_bytes(b"image-one")
    (data_dir / "copy.png").write_bytes(b"image-one")
    nested = data_dir / "cats"
    nested.mkdir()
    (nested / "cat.jpg").write_bytes(b"cat")
    (data_dir / ".thumb_cache").mkdir()
    (data_dir / ".thumb_cache" / "hidden.png").write_bytes(b"hidden")

    monkeypatch.setenv("DATA_FOLDER", str(data_dir))
    monkeypatch.setenv("AUTH_TYPE", auth_type)
    monkeypatch.setenv("ADMIN_PASSWORD", "pass123" if auth_type == "local" else "")
    monkeypatch.setenv("OIDC_ENABLED", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret-for-ci")
    if api_keys is None:
        monkeypatch.delenv("LLM_API_KEYS", raising=False)
    else:
        monkeypatch.setenv("LLM_API_KEYS", api_keys)

    for mod in ("auth", "app"):
        if mod in sys.modules:
            del sys.modules[mod]

    app_module = importlib.import_module("app")
    app_module.DATA_FOLDER = data_dir
    app_module.THUMBNAIL_CACHE_DIR = data_dir / ".thumb_cache"
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client(), data_dir


def _auth(token="agent-key"):
    return {"Authorization": f"Bearer {token}"}


def test_llm_api_requires_configured_valid_bearer_token(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path)

    assert client.get("/api/llm/images").status_code == 401
    assert client.get("/api/llm/images", headers=_auth("wrong")).status_code == 401
    assert client.get("/api/llm/images", headers=_auth()).status_code == 200


def test_llm_api_reports_unconfigured_keys(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path, api_keys=None, auth_type="none")

    resp = client.get("/api/llm/images")

    assert resp.status_code == 403
    assert resp.get_json()["error"] == "LLM API keys are not configured"


def test_llm_images_search_metadata_recent_and_folders(monkeypatch, tmp_path):
    client, _ = _build_client(monkeypatch, tmp_path)

    images = client.get("/api/llm/images?q=cat", headers=_auth())
    assert images.status_code == 200
    payload = images.get_json()
    assert payload["count"] == 1
    assert payload["images"][0]["rel_path"] == "cats/cat.jpg"

    image = client.get("/api/llm/image/cats/cat.jpg", headers=_auth())
    assert image.status_code == 200
    assert image.get_json()["media_type"] == "image"

    recent = client.get("/api/llm/recent?limit=2", headers=_auth())
    assert recent.status_code == 200
    assert recent.get_json()["count"] == 2

    folders = client.get("/api/llm/folders", headers=_auth())
    assert folders.status_code == 200
    assert any(folder["rel_path"] == "cats" for folder in folders.get_json()["folders"])


def test_llm_delete_and_bulk_delete_do_not_require_csrf(monkeypatch, tmp_path):
    client, data_dir = _build_client(monkeypatch, tmp_path)

    delete = client.post("/api/llm/delete", json={"rel_path": "cats/cat.jpg"}, headers=_auth())
    assert delete.status_code == 200
    assert delete.get_json()["deleted"] is True
    assert not (data_dir / "cats" / "cat.jpg").exists()

    bulk = client.post("/api/llm/bulk-delete", json={"rel_paths": ["sample.png"]}, headers=_auth())
    assert bulk.status_code == 200
    assert bulk.get_json()["deleted"] == ["sample.png"]
    assert not (data_dir / "sample.png").exists()


def test_llm_dedup_dry_run_and_remove(monkeypatch, tmp_path):
    client, data_dir = _build_client(monkeypatch, tmp_path)

    dry_run = client.post("/api/llm/dedup", json={}, headers=_auth())
    assert dry_run.status_code == 200
    dry_payload = dry_run.get_json()
    assert dry_payload["dry_run"] is True
    assert dry_payload["group_count"] == 1
    assert dry_payload["removed"] == []

    remove = client.post("/api/llm/dedup", json={"remove": True}, headers=_auth())
    assert remove.status_code == 200
    payload = remove.get_json()
    assert payload["dry_run"] is False
    assert payload["removed"] == ["sample.png"]
    assert not (data_dir / "sample.png").exists()


def test_llm_tags_and_task_run(monkeypatch, tmp_path):
    monkeypatch.setenv("WEBHOOK_ENABLED", "true")
    monkeypatch.setenv("WEBHOOK_TASK_ECHO", "python3 -c \"import sys;print(sys.argv[1])\" {params.value}")
    client, _ = _build_client(monkeypatch, tmp_path)

    tags = client.post(
        "/api/llm/tags",
        json={"rel_path": "sample.png", "tag": "miso", "action": "add"},
        headers=_auth(),
    )
    assert tags.status_code == 200
    assert tags.get_json()["updated"] == ["sample.png"]

    task = client.post(
        "/api/llm/task/run",
        json={"task": "echo", "params": {"value": "hello"}},
        headers=_auth(),
    )
    assert task.status_code == 200
    assert task.get_json()["stdout"].strip() == "hello"
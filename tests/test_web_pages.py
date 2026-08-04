import pytest

pytest.importorskip("fastapi", reason="fastapi not installed in this environment")
fastapi_testclient = pytest.importorskip("starlette.testclient")


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path / "outputs"))
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    yield fastapi_testclient.TestClient(app)
    get_settings.cache_clear()


def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Upload a Document" in response.text


def test_upload_page_renders(client):
    response = client.get("/upload")
    assert response.status_code == 200
    assert "upload-form" in response.text


def test_progress_page_renders(client):
    response = client.get("/progress")
    assert response.status_code == 200
    assert "progress-root" in response.text


def test_results_page_renders(client):
    response = client.get("/results/some-document-id")
    assert response.status_code == 200
    assert "results-content" in response.text


def test_error_page_renders(client):
    response = client.get("/error")
    assert response.status_code == 200
    assert "error-title" in response.text


def test_unknown_page_returns_html_404(client):
    response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Page Not Found" in response.text


def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/v1/this-does-not-exist")
    assert response.status_code == 404
    assert "application/json" in response.headers["content-type"]


def test_static_css_is_served(client):
    response = client.get("/static/css/style.css")
    assert response.status_code == 200


def test_swagger_docs_load(client):
    response = client.get("/docs")
    assert response.status_code == 200

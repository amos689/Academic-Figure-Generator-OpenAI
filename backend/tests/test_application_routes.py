import pytest

from app import main


def test_workbench_routes_are_registered():
    routes = main.create_app().openapi()["paths"]
    for path in (
        "/configuration", "/configuration/check", "/styles", "/jobs",
        "/projects/{project_id}/prompt-jobs", "/prompts/{prompt_id}/exports",
    ):
        assert f"/api/v1{path}" in routes


def test_missing_required_router_fails_startup(monkeypatch):
    original = main.importlib.import_module

    def missing_configuration(name, *args, **kwargs):
        if name == "app.api.v1.configuration":
            raise ImportError("missing dependency")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(main.importlib, "import_module", missing_configuration)
    with pytest.raises(ImportError, match="missing dependency"):
        main.create_app()

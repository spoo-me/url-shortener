"""Unit tests for shared.app_registry.load_app_registry."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from shared.app_registry import load_app_registry


@pytest.fixture()
def yaml_file(tmp_path: Path) -> Path:
    """Return a path to a temp YAML file (caller writes content)."""
    return tmp_path / "apps.yaml"


def _write(path: Path, content: str) -> Path:
    path.write_text(dedent(content).lstrip())
    return path


class TestLoadAppRegistry:
    def test_loads_valid_registry(self, yaml_file: Path):
        _write(
            yaml_file,
            """
            apps:
              spoo-snap:
                name: Spoo Snap
                description: Browser extension
                verified: true
                status: live
                type: device_auth
              spoo-cli:
                name: Spoo CLI
                description: Terminal tool
                status: coming_soon
                type: device_auth
            """,
        )
        registry = load_app_registry(yaml_file)
        assert len(registry) == 2
        assert "spoo-snap" in registry
        assert "spoo-cli" in registry
        assert registry["spoo-snap"].name == "Spoo Snap"
        assert registry["spoo-snap"].is_live_device_app() is True
        assert registry["spoo-cli"].is_live_device_app() is False

    def test_returns_empty_dict_when_file_missing(self, tmp_path: Path):
        registry = load_app_registry(tmp_path / "nope.yaml")
        assert registry == {}

    def test_returns_empty_dict_on_invalid_yaml(self, yaml_file: Path):
        _write(yaml_file, ":::not valid yaml:::")
        registry = load_app_registry(yaml_file)
        assert registry == {}

    def test_returns_empty_dict_when_no_apps_key(self, yaml_file: Path):
        _write(yaml_file, "something_else: true\n")
        registry = load_app_registry(yaml_file)
        assert registry == {}

    def test_returns_empty_dict_when_apps_is_empty(self, yaml_file: Path):
        _write(yaml_file, "apps: {}\n")
        registry = load_app_registry(yaml_file)
        assert registry == {}

    def test_skips_invalid_entries(self, yaml_file: Path):
        _write(
            yaml_file,
            """
            apps:
              good-app:
                name: Good
                description: Works fine
              bad-app:
                name: ""
                description: ""
            """,
        )
        registry = load_app_registry(yaml_file)
        assert "good-app" in registry
        assert "bad-app" not in registry

    def test_validates_icon_for_live_apps(self, yaml_file: Path, tmp_path: Path):
        _write(
            yaml_file,
            """
            apps:
              my-app:
                name: My App
                description: Has an icon
                icon: my-icon.svg
                status: live
                type: device_auth
            """,
        )
        # Icon doesn't exist — should still load (just warns)
        registry = load_app_registry(yaml_file)
        assert "my-app" in registry

    def test_preserves_all_fields(self, yaml_file: Path):
        _write(
            yaml_file,
            """
            apps:
              test-app:
                name: Test
                description: Full fields
                verified: true
                status: live
                type: device_auth
                redirect_uris:
                  - http://localhost:9000/cb
                links:
                  chrome: https://chrome.google.com
                permissions:
                  - Access your account
                  - Create short URLs
            """,
        )
        registry = load_app_registry(yaml_file)
        app = registry["test-app"]
        assert app.verified is True
        assert app.redirect_uris == ["http://localhost:9000/cb"]
        assert app.links == {"chrome": "https://chrome.google.com"}
        assert len(app.permissions) == 2

    def test_returns_empty_dict_for_non_dict_file(self, yaml_file: Path):
        _write(yaml_file, "- just\n- a\n- list\n")
        registry = load_app_registry(yaml_file)
        assert registry == {}

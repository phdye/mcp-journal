"""Tests for configuration loading."""

import tempfile
from pathlib import Path

import pytest

from mcp_journal.config import (
    ProjectConfig,
    dict_to_config,
    find_config_file,
    load_config,
    load_json_config,
    load_python_config,
)


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestFindConfigFile:
    """Tests for find_config_file."""

    def test_finds_python_config(self, temp_project):
        """Python config is found first."""
        (temp_project / "journal_config.py").write_text("CONFIG = {}")
        (temp_project / "journal_config.toml").write_text("")

        found = find_config_file(temp_project)
        assert found.name == "journal_config.py"

    def test_finds_toml_config(self, temp_project):
        """TOML config is found if no Python config."""
        (temp_project / "journal_config.toml").write_text("")

        found = find_config_file(temp_project)
        assert found.name == "journal_config.toml"

    def test_finds_json_config(self, temp_project):
        """JSON config is found if no Python/TOML."""
        (temp_project / "journal_config.json").write_text("{}")

        found = find_config_file(temp_project)
        assert found.name == "journal_config.json"

    def test_finds_dotfile_config(self, temp_project):
        """Dotfile configs are found."""
        (temp_project / ".journal.toml").write_text("")

        found = find_config_file(temp_project)
        assert found.name == ".journal.toml"

    def test_returns_none_if_no_config(self, temp_project):
        """Returns None if no config file found."""
        found = find_config_file(temp_project)
        assert found is None


class TestLoadJsonConfig:
    """Tests for load_json_config."""

    def test_loads_json(self, temp_project):
        """Loads JSON config file."""
        config_file = temp_project / "config.json"
        config_file.write_text('{"project": {"name": "test"}}')

        data = load_json_config(config_file)
        assert data["project"]["name"] == "test"


class TestLoadPythonConfig:
    """Tests for load_python_config."""

    def test_loads_config_dict(self, temp_project):
        """Loads CONFIG dict from Python file."""
        config_file = temp_project / "journal_config.py"
        config_file.write_text('''
CONFIG = {
    "project": {"name": "python-project"},
}
''')

        data, hooks, tools = load_python_config(config_file)
        assert data["project"]["name"] == "python-project"

    def test_extracts_hooks(self, temp_project):
        """Extracts hook_* functions."""
        config_file = temp_project / "journal_config.py"
        config_file.write_text('''
CONFIG = {}

def hook_pre_append(entry, fields):
    return entry

def hook_post_append(entry):
    pass
''')

        data, hooks, tools = load_python_config(config_file)
        assert "pre_append" in hooks
        assert "post_append" in hooks
        assert callable(hooks["pre_append"])

    def test_extracts_custom_tools(self, temp_project):
        """Extracts custom_tool_* functions."""
        config_file = temp_project / "journal_config.py"
        config_file.write_text('''
CONFIG = {}

def custom_tool_my_tool(engine, params):
    return {"result": "ok"}

def custom_tool_another(engine, params):
    return {}
''')

        data, hooks, tools = load_python_config(config_file)
        assert "my_tool" in tools
        assert "another" in tools
        assert callable(tools["my_tool"])


class TestDictToConfig:
    """Tests for dict_to_config."""

    def test_sets_project_name(self, temp_project):
        """Sets project name from dict."""
        data = {"project": {"name": "my-project"}}
        config = dict_to_config(data, temp_project)
        assert config.project_name == "my-project"

    def test_sets_directories(self, temp_project):
        """Sets custom directories."""
        data = {
            "directories": {
                "journal": "my-journal",
                "configs": "my-configs",
            }
        }
        config = dict_to_config(data, temp_project)
        assert config.journal_dir == "my-journal"
        assert config.configs_dir == "my-configs"

    def test_sets_tracking(self, temp_project):
        """Sets tracking options."""
        data = {
            "tracking": {
                "config_patterns": ["*.yaml"],
                "log_categories": ["build", "test"],
                "stages": ["dev", "prod"],
            }
        }
        config = dict_to_config(data, temp_project)
        assert config.config_patterns == ["*.yaml"]
        assert config.log_categories == ["build", "test"]
        assert config.stages == ["dev", "prod"]

    def test_sets_version_commands(self, temp_project):
        """Sets version commands."""
        data = {
            "versions": {
                "python": "python --version",
                "node": {"command": "node -v", "regex": r"v(\d+)"},
            }
        }
        config = dict_to_config(data, temp_project)
        assert len(config.version_commands) == 2

        python_cmd = next(v for v in config.version_commands if v.name == "python")
        assert python_cmd.command == "python --version"
        assert python_cmd.parse_regex is None

        node_cmd = next(v for v in config.version_commands if v.name == "node")
        assert node_cmd.command == "node -v"
        assert node_cmd.parse_regex == r"v(\d+)"


class TestLoadConfig:
    """Tests for load_config."""

    def test_returns_defaults_without_config(self, temp_project):
        """Returns default config if no config file."""
        config = load_config(temp_project)
        assert config.project_name == "unnamed"
        assert config.project_root == temp_project

    def test_loads_toml_config(self, temp_project):
        """Loads TOML configuration."""
        config_file = temp_project / "journal_config.toml"
        config_file.write_text('''
[project]
name = "toml-project"

[tracking]
stages = ["a", "b"]
''')

        config = load_config(temp_project)
        assert config.project_name == "toml-project"
        assert config.stages == ["a", "b"]

    def test_loads_json_config(self, temp_project):
        """Loads JSON configuration."""
        config_file = temp_project / "journal_config.json"
        config_file.write_text('{"project": {"name": "json-project"}}')

        config = load_config(temp_project)
        assert config.project_name == "json-project"

    def test_loads_python_config_with_tools(self, temp_project):
        """Loads Python configuration with custom tools."""
        config_file = temp_project / "journal_config.py"
        config_file.write_text('''
CONFIG = {"project": {"name": "py-project"}}

def custom_tool_test(engine, params):
    return {"ok": True}
''')

        config = load_config(temp_project)
        assert config.project_name == "py-project"
        assert "test" in config.custom_tools

    def test_explicit_config_path(self, temp_project):
        """Uses explicit config path if provided."""
        config_file = temp_project / "custom" / "my-config.json"
        config_file.parent.mkdir()
        config_file.write_text('{"project": {"name": "explicit"}}')

        config = load_config(temp_project, config_path=config_file)
        assert config.project_name == "explicit"

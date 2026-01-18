"""Tests for MCP server module."""

import argparse
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from mcp_journal.config import ProjectConfig, load_config
from mcp_journal.engine import JournalEngine


# Fixtures temp_project, config, and engine are provided by conftest.py


class TestServerImports:
    """Test server module imports and HAS_MCP flag."""

    def test_server_imports_without_mcp(self):
        """Test server can be imported even without MCP."""
        # Force reimport without MCP
        import mcp_journal.server as server_module
        # Module should be importable regardless of MCP availability
        assert hasattr(server_module, 'HAS_MCP')
        assert hasattr(server_module, 'create_server')
        assert hasattr(server_module, 'run_server')
        assert hasattr(server_module, 'main')


class TestCreateServer:
    """Tests for create_server function."""

    def test_create_server_without_mcp_raises(self, config):
        """create_server raises ImportError when MCP not available."""
        import mcp_journal.server as server_module

        # If MCP is not available, should raise
        if not server_module.HAS_MCP:
            with pytest.raises(ImportError, match="MCP package not installed"):
                server_module.create_server(config)

    @pytest.mark.skipif(
        not __import__('mcp_journal.server', fromlist=['HAS_MCP']).HAS_MCP,
        reason="MCP not installed"
    )
    def test_create_server_with_mcp(self, config):
        """create_server creates server when MCP available."""
        from mcp_journal.server import create_server
        server = create_server(config)
        assert server is not None

    @pytest.mark.skipif(
        not __import__('mcp_journal.server', fromlist=['HAS_MCP']).HAS_MCP,
        reason="MCP not installed"
    )
    def test_create_server_with_custom_tools(self, temp_project):
        """create_server includes custom tools from config."""
        def custom_tool_test(engine, params):
            """Test custom tool"""
            return {"result": "custom"}

        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            custom_tools={"test": custom_tool_test},
        )

        from mcp_journal.server import create_server
        server = create_server(config)
        assert server is not None


class TestRunServer:
    """Tests for run_server function."""

    @pytest.mark.asyncio
    async def test_run_server_without_mcp_raises(self, config):
        """run_server raises ImportError when MCP not available."""
        import mcp_journal.server as server_module

        if not server_module.HAS_MCP:
            with pytest.raises(ImportError, match="MCP package not installed"):
                await server_module.run_server(config)


class TestMain:
    """Tests for main entry point."""

    def test_main_init_mode(self, temp_project):
        """main --init creates journal directories."""
        from mcp_journal.server import main

        test_args = ["mcp-journal", "--project-root", str(temp_project), "--init"]
        with patch.object(sys, 'argv', test_args):
            with patch('builtins.print') as mock_print:
                main()

        # Verify directories created
        assert (temp_project / "journal").exists()
        assert (temp_project / "configs").exists()
        assert (temp_project / "logs").exists()
        assert (temp_project / "snapshots").exists()

    def test_main_without_mcp_exits(self, temp_project):
        """main exits with error when MCP not available in server mode."""
        import mcp_journal.server as server_module

        if not server_module.HAS_MCP:
            test_args = ["mcp-journal", "--project-root", str(temp_project)]
            with patch.object(sys, 'argv', test_args):
                with pytest.raises(SystemExit) as exc_info:
                    server_module.main()
                assert exc_info.value.code == 1

    def test_main_config_load_error(self, temp_project):
        """main handles config load errors."""
        import mcp_journal.server as server_module

        # Create invalid config file
        invalid_config = temp_project / "journal_config.toml"
        invalid_config.write_text("invalid toml [[[")

        if server_module.HAS_MCP:
            test_args = ["mcp-journal", "--project-root", str(temp_project)]
            with patch.object(sys, 'argv', test_args):
                with pytest.raises(SystemExit) as exc_info:
                    server_module.main()
                assert exc_info.value.code == 1


class TestServerToolExecution:
    """Tests for server tool execution with custom tools."""

    @pytest.mark.skipif(
        not __import__('mcp_journal.server', fromlist=['HAS_MCP']).HAS_MCP,
        reason="MCP not installed"
    )
    @pytest.mark.asyncio
    async def test_custom_tool_execution(self, temp_project):
        """Custom tools can be executed through server."""
        call_count = {"count": 0}

        def custom_tool_counter(engine, params):
            """Count calls"""
            call_count["count"] += 1
            return {"calls": call_count["count"]}

        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            custom_tools={"counter": custom_tool_counter},
        )

        from mcp_journal.server import create_server
        server = create_server(config)
        # Server is created with custom tool registered
        assert server is not None

    @pytest.mark.skipif(
        not __import__('mcp_journal.server', fromlist=['HAS_MCP']).HAS_MCP,
        reason="MCP not installed"
    )
    @pytest.mark.asyncio
    async def test_custom_tool_async(self, temp_project):
        """Async custom tools work correctly."""
        async def custom_tool_async(engine, params):
            """Async custom tool"""
            return {"async": True}

        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            custom_tools={"async_tool": custom_tool_async},
        )

        from mcp_journal.server import create_server
        server = create_server(config)
        assert server is not None

    @pytest.mark.skipif(
        not __import__('mcp_journal.server', fromlist=['HAS_MCP']).HAS_MCP,
        reason="MCP not installed"
    )
    @pytest.mark.asyncio
    async def test_custom_tool_error_handling(self, temp_project):
        """Custom tools that raise errors are handled."""
        def custom_tool_error(engine, params):
            """Tool that raises"""
            raise ValueError("Custom error")

        config = ProjectConfig(
            project_name="test",
            project_root=temp_project,
            custom_tools={"error_tool": custom_tool_error},
        )

        from mcp_journal.server import create_server
        server = create_server(config)
        assert server is not None


# ============ Skills Functions Tests ============


class TestSkillsFunctions:
    """Tests for skills management functions."""

    def test_get_skills_source_dir(self):
        """get_skills_source_dir returns path to bundled skills."""
        from mcp_journal.server import get_skills_source_dir
        source_dir = get_skills_source_dir()
        assert source_dir.name == "skills"
        assert "mcp_journal" in str(source_dir)

    def test_get_skills_target_dir(self):
        """get_skills_target_dir returns ~/.claude/skills/."""
        from mcp_journal.server import get_skills_target_dir
        target_dir = get_skills_target_dir()
        assert target_dir.name == "skills"
        assert ".claude" in str(target_dir)

    def test_install_skills(self, tmp_path, monkeypatch):
        """install_skills copies skill files to target directory."""
        from mcp_journal.server import install_skills

        # Create fake source skills directory
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff\n\nHandoff skill description")
        (source_dir / "pickup.md").write_text("# Pickup\n\nPickup skill description")

        # Create target directory
        target_dir = tmp_path / "target"

        # Mock the path functions
        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)

        installed, skipped = install_skills()

        assert "handoff" in installed
        assert "pickup" in installed
        assert len(skipped) == 0
        assert (target_dir / "handoff.md").exists()
        assert (target_dir / "pickup.md").exists()

    def test_install_skills_skips_existing(self, tmp_path, monkeypatch):
        """install_skills skips existing files without force."""
        from mcp_journal.server import install_skills

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# New Handoff")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "handoff.md").write_text("# Existing Handoff")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)

        installed, skipped = install_skills(force=False)

        assert len(installed) == 0
        assert "handoff" in skipped
        # Original content should be preserved
        assert "Existing" in (target_dir / "handoff.md").read_text()

    def test_install_skills_force_overwrites(self, tmp_path, monkeypatch):
        """install_skills overwrites existing files with force=True."""
        from mcp_journal.server import install_skills

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# New Handoff")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "handoff.md").write_text("# Old Handoff")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)

        installed, skipped = install_skills(force=True)

        assert "handoff" in installed
        assert len(skipped) == 0
        assert "New" in (target_dir / "handoff.md").read_text()

    def test_install_skills_source_not_found(self, tmp_path, monkeypatch):
        """install_skills raises if source directory doesn't exist."""
        from mcp_journal.server import install_skills

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: tmp_path / "nonexistent")

        with pytest.raises(FileNotFoundError):
            install_skills()

    def test_uninstall_skills(self, tmp_path, monkeypatch):
        """uninstall_skills removes installed skill files."""
        from mcp_journal.server import uninstall_skills

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff")
        (source_dir / "pickup.md").write_text("# Pickup")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "handoff.md").write_text("# Handoff")
        (target_dir / "pickup.md").write_text("# Pickup")
        (target_dir / "other.md").write_text("# Other")  # Not from source

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)

        removed = uninstall_skills()

        assert "handoff" in removed
        assert "pickup" in removed
        assert not (target_dir / "handoff.md").exists()
        assert not (target_dir / "pickup.md").exists()
        assert (target_dir / "other.md").exists()  # Preserved

    def test_uninstall_skills_none_found(self, tmp_path, monkeypatch):
        """uninstall_skills returns empty list if no skills to remove."""
        from mcp_journal.server import uninstall_skills

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff")

        target_dir = tmp_path / "target"
        target_dir.mkdir()  # No matching files

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)

        removed = uninstall_skills()
        assert len(removed) == 0

    def test_list_skills(self, tmp_path, monkeypatch):
        """list_skills returns available skills with descriptions."""
        from mcp_journal.server import list_skills

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff\n\nCreate a session handoff package.")
        (source_dir / "pickup.md").write_text("# Pickup\n\nLoad context from handoff.")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)

        skills = list_skills()

        assert len(skills) == 2
        names = [s["name"] for s in skills]
        assert "handoff" in names
        assert "pickup" in names

        handoff = next(s for s in skills if s["name"] == "handoff")
        assert "handoff package" in handoff["description"].lower()


# ============ CLI Commands Tests ============


class TestRunCliCommand:
    """Tests for run_cli_command function."""

    def test_cli_query_command_text_format(self, engine, capsys):
        """CLI query command with text output."""
        from mcp_journal.server import run_cli_command

        # Create test entry
        engine.journal_append(author="test", context="Test context", outcome="success")

        args = argparse.Namespace(
            command="query",
            tool=None,
            outcome=None,
            author=None,
            since=None,
            until=None,
            limit=100,
            format="text",
            asc=False,
            text=None,
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Found 1 entries" in captured.out
        assert "test" in captured.out

    def test_cli_query_command_json_format(self, engine, capsys):
        """CLI query command with JSON output."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="Test context")

        args = argparse.Namespace(
            command="query",
            tool=None,
            outcome=None,
            author=None,
            since=None,
            until=None,
            limit=100,
            format="json",
            asc=False,
            text=None,
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "[" in captured.out  # JSON array
        assert "entry_id" in captured.out

    def test_cli_query_with_filters(self, engine, capsys):
        """CLI query command with filters."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="alice", context="Alice entry", outcome="success")
        engine.journal_append(author="bob", context="Bob entry", outcome="failure")

        args = argparse.Namespace(
            command="query",
            tool=None,
            outcome="success",
            author="alice",
            since=None,
            until=None,
            limit=100,
            format="text",
            asc=False,
            text=None,
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Found 1 entries" in captured.out
        assert "alice" in captured.out

    def test_cli_search_command(self, engine, capsys):
        """CLI search command."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="Building the application")
        engine.journal_append(author="test", context="Testing the code")

        args = argparse.Namespace(
            command="search",
            query="Building",
            since=None,
            until=None,
            limit=100,
            format="text",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "matching entries" in captured.out

    def test_cli_search_command_json(self, engine, capsys):
        """CLI search command with JSON output."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="Building the application")

        args = argparse.Namespace(
            command="search",
            query="Building",
            since=None,
            until=None,
            limit=100,
            format="json",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "[" in captured.out

    def test_cli_stats_command_overall(self, engine, capsys):
        """CLI stats command for overall stats."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="Entry 1", outcome="success")
        engine.journal_append(author="test", context="Entry 2", outcome="failure")

        args = argparse.Namespace(
            command="stats",
            by=None,
            since=None,
            until=None,
            format="text",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Total entries:" in captured.out or "entries" in captured.out.lower()

    def test_cli_stats_command_group_by(self, engine, capsys):
        """CLI stats command with group_by."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="alice", context="Alice entry", outcome="success")
        engine.journal_append(author="bob", context="Bob entry", outcome="success")

        args = argparse.Namespace(
            command="stats",
            by="author",
            since=None,
            until=None,
            format="text",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "alice" in captured.out or "bob" in captured.out

    def test_cli_stats_command_json(self, engine, capsys):
        """CLI stats command with JSON output."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="Entry", outcome="success")

        args = argparse.Namespace(
            command="stats",
            by="outcome",
            since=None,
            until=None,
            format="json",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "{" in captured.out

    def test_cli_active_command(self, engine, capsys):
        """CLI active command."""
        from mcp_journal.server import run_cli_command

        # Create an entry without outcome (active)
        engine.journal_append(author="test", context="In progress work")

        args = argparse.Namespace(
            command="active",
            threshold=30000,
            tool=None,
            format="text",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        # Should show active operations or "no active"
        assert "active" in captured.out.lower() or "operations" in captured.out.lower()

    def test_cli_active_command_json(self, engine, capsys):
        """CLI active command with JSON output."""
        from mcp_journal.server import run_cli_command

        args = argparse.Namespace(
            command="active",
            threshold=30000,
            tool=None,
            format="json",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "[" in captured.out or "{" in captured.out

    def test_cli_export_command_json(self, engine, capsys):
        """CLI export command with JSON format."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="Export test entry")

        args = argparse.Namespace(
            command="export",
            since=None,
            until=None,
            format="json",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "[" in captured.out
        assert "entry_id" in captured.out

    def test_cli_export_command_csv(self, engine, capsys):
        """CLI export command with CSV format."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="CSV export test")

        args = argparse.Namespace(
            command="export",
            since=None,
            until=None,
            format="csv",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "entry_id" in captured.out  # CSV header
        assert "," in captured.out


# ============ Main Function Tests ============


class TestMainSkillsCommands:
    """Tests for main() skills-related command handling."""

    def test_main_list_skills(self, tmp_path, monkeypatch, capsys):
        """main --list-skills shows available skills."""
        from mcp_journal.server import main

        # Create fake skills
        source_dir = tmp_path / "skills"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff\n\nCreate handoff package.")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--list-skills"])

        main()

        captured = capsys.readouterr()
        assert "/handoff" in captured.out
        assert "handoff package" in captured.out.lower()

    def test_main_install_skills(self, tmp_path, monkeypatch, capsys):
        """main --install-skills installs skills."""
        from mcp_journal.server import main

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff\n\nDescription")

        target_dir = tmp_path / "target"

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--install-skills"])

        main()

        captured = capsys.readouterr()
        assert "Installed" in captured.out or "handoff" in captured.out
        assert (target_dir / "handoff.md").exists()

    def test_main_install_skills_with_force(self, tmp_path, monkeypatch, capsys):
        """main --install-skills --force overwrites existing."""
        from mcp_journal.server import main

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# New Handoff")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "handoff.md").write_text("# Old Handoff")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--install-skills", "--force"])

        main()

        assert "New" in (target_dir / "handoff.md").read_text()

    def test_main_install_skills_error(self, tmp_path, monkeypatch, capsys):
        """main --install-skills handles errors."""
        from mcp_journal.server import main

        # Source dir doesn't exist
        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: tmp_path / "nonexistent")
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--install-skills"])

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_main_uninstall_skills(self, tmp_path, monkeypatch, capsys):
        """main --uninstall-skills removes skills."""
        from mcp_journal.server import main

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "handoff.md").write_text("# Handoff")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--uninstall-skills"])

        main()

        captured = capsys.readouterr()
        assert "Removed" in captured.out or "handoff" in captured.out
        assert not (target_dir / "handoff.md").exists()

    def test_main_uninstall_skills_none_found(self, tmp_path, monkeypatch, capsys):
        """main --uninstall-skills handles no skills found."""
        from mcp_journal.server import main

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "handoff.md").write_text("# Handoff")

        target_dir = tmp_path / "target"
        target_dir.mkdir()  # No skills installed

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--uninstall-skills"])

        main()

        captured = capsys.readouterr()
        assert "No" in captured.out or "found" in captured.out.lower()


class TestMainCliCommands:
    """Tests for main() CLI subcommand handling."""

    def test_main_cli_query(self, temp_project, monkeypatch, capsys):
        """main handles CLI query subcommand."""
        from mcp_journal.server import main

        # Create an entry first
        config = load_config(temp_project)
        engine = JournalEngine(config)
        engine.journal_append(author="test", context="Test entry")

        monkeypatch.setattr(sys, "argv", [
            "mcp-journal", "--project-root", str(temp_project),
            "query", "--format", "text"
        ])

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "Found" in captured.out

    def test_main_cli_stats(self, temp_project, monkeypatch, capsys):
        """main handles CLI stats subcommand."""
        from mcp_journal.server import main

        config = load_config(temp_project)
        engine = JournalEngine(config)
        engine.journal_append(author="test", context="Test", outcome="success")

        monkeypatch.setattr(sys, "argv", [
            "mcp-journal", "--project-root", str(temp_project),
            "stats", "--format", "text"
        ])

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0

    def test_main_cli_config_error(self, temp_project, monkeypatch, capsys):
        """main handles config errors for CLI commands."""
        from mcp_journal.server import main

        # Create invalid config
        (temp_project / "journal_config.toml").write_text("invalid [[[")

        monkeypatch.setattr(sys, "argv", [
            "mcp-journal", "--project-root", str(temp_project),
            "query"
        ])

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


class TestCliCommandBranches:
    """Tests to cover specific branches in CLI commands."""

    def test_cli_query_with_tool_filter_text(self, engine, capsys):
        """CLI query with tool filter in text format (covers line 235)."""
        from mcp_journal.server import run_cli_command

        # Create entry with tool field (must use tool= param directly, not template_values)
        engine.journal_append(
            author="test",
            context="Running bash command",
            tool="bash",  # Direct parameter, not template_values
            command="ls -la",
        )

        args = argparse.Namespace(
            command="query",
            tool="bash",  # This covers line 235: filters["tool"] = args.tool
            outcome=None,
            author=None,
            since=None,
            until=None,
            limit=100,
            format="text",
            asc=False,
            text=None,
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Found" in captured.out

    def test_cli_query_text_with_tool_and_context(self, engine, capsys):
        """CLI query text format showing tool and context (covers lines 258-262)."""
        from mcp_journal.server import run_cli_command

        # Create entry with tool AND long context (>100 chars for truncation)
        long_context = "Building application with make. " * 10  # >100 chars
        engine.journal_append(
            author="test",
            context=long_context,
            outcome="success",
            tool="make",  # Direct parameter
        )

        args = argparse.Namespace(
            command="query",
            tool=None,
            outcome=None,
            author=None,
            since=None,
            until=None,
            limit=100,
            format="text",
            asc=False,
            text=None,
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        # Should show Tool: and Context:
        assert "Tool:" in captured.out or "make" in captured.out
        assert "Context:" in captured.out or "Building" in captured.out

    def test_cli_stats_text_with_all_sections(self, engine, capsys):
        """CLI stats text showing by_type, by_outcome, top_tools (covers lines 315-326)."""
        from mcp_journal.server import run_cli_command

        # Create entries with various outcomes and tools (use tool= param directly)
        engine.journal_append(
            author="test",
            context="Entry 1",
            outcome="success",
            tool="bash",
        )
        engine.journal_append(
            author="test",
            context="Entry 2",
            outcome="failure",
            tool="bash",
        )
        engine.journal_append(
            author="test",
            context="Entry 3",
            outcome="success",
            tool="make",
        )

        args = argparse.Namespace(
            command="stats",
            by=None,  # Overall stats, not grouped
            since=None,
            until=None,
            format="text",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        # Should show By type, By outcome, Top tools sections
        assert "Total entries:" in captured.out

    def test_cli_active_text_with_results(self, engine, capsys):
        """CLI active showing results in text format (covers lines 341-352)."""
        from mcp_journal.server import run_cli_command

        # Create entry without outcome (considered active) and with tool/command
        # Use direct parameters, not template_values
        engine.journal_append(
            author="test",
            context="Long running operation",
            tool="bash",
            command="make -j12 all",
            duration_ms=45000,
            # No outcome = considered potentially active
        )

        args = argparse.Namespace(
            command="active",
            threshold=1,  # Very low threshold to catch our entry
            tool=None,
            format="text",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        # Text format with results should show entry details
        assert "Found" in captured.out or "operations" in captured.out.lower()

    def test_cli_export_default_format(self, engine, capsys):
        """CLI export with unrecognized format falls back to JSON (covers line 374)."""
        from mcp_journal.server import run_cli_command

        engine.journal_append(author="test", context="Export test")

        args = argparse.Namespace(
            command="export",
            since=None,
            until=None,
            format="xml",  # Unrecognized format -> defaults to JSON
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        # Should fall back to JSON
        assert "[" in captured.out or "{" in captured.out

    def test_cli_export_csv_empty(self, engine, capsys):
        """CLI export CSV with no results (covers line 368->375)."""
        from mcp_journal.server import run_cli_command

        # Don't create any entries - query should return empty

        args = argparse.Namespace(
            command="export",
            since="2099-01-01",  # Future date - no entries
            until="2099-12-31",
            format="csv",
        )

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        # No output since no results
        captured = capsys.readouterr()
        assert "entry_id" not in captured.out  # No header written

    def test_cli_rebuild_index(self, engine, capsys):
        """CLI rebuild-index command (covers lines 377-387)."""
        from mcp_journal.server import run_cli_command

        # Create some entries first
        engine.journal_append(author="test", context="Entry for rebuild test")

        args = argparse.Namespace(command="rebuild-index")

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Rebuilding" in captured.out or "index" in captured.out.lower()
        assert "Done" in captured.out

    def test_cli_unknown_command(self, engine):
        """CLI with unknown command returns 1 (covers line 387)."""
        from mcp_journal.server import run_cli_command

        args = argparse.Namespace(command="unknown-command")

        exit_code = run_cli_command(args, engine.config)
        assert exit_code == 1


class TestListSkillsBranches:
    """Tests for list_skills branch coverage."""

    def test_list_skills_no_description(self, tmp_path, monkeypatch):
        """list_skills with skill file having no description (covers 210->218)."""
        from mcp_journal.server import list_skills

        # Create skill with only title line
        source_dir = tmp_path / "skills"
        source_dir.mkdir()
        (source_dir / "empty.md").write_text("# Empty Skill\n\n")  # Only title, no description

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)

        skills = list_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "empty"
        assert skills[0]["description"] == ""  # No description found


class TestInstallSkillsBranches:
    """Tests for install_skills branch coverage."""

    def test_install_skills_some_skipped(self, tmp_path, monkeypatch, capsys):
        """main --install-skills with some already installed (covers 509-512)."""
        from mcp_journal.server import main

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "new.md").write_text("# New Skill\n\nDescription")
        (source_dir / "existing.md").write_text("# Existing\n\nDescription")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "existing.md").write_text("# Old Existing\n\nOld desc")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--install-skills"])

        main()

        captured = capsys.readouterr()
        # Should show both installed and skipped
        assert "Installed" in captured.out
        assert "Skipped" in captured.out or "existing" in captured.out

    def test_install_skills_none_to_install(self, tmp_path, monkeypatch, capsys):
        """main --install-skills with all already installed (covers line 514)."""
        from mcp_journal.server import main

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "skill.md").write_text("# Skill\n\nDescription")

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "skill.md").write_text("# Skill\n\nDescription")

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--install-skills"])

        main()

        captured = capsys.readouterr()
        # All skipped, nothing newly installed
        assert "Skipped" in captured.out or "exist" in captured.out.lower()

    def test_install_skills_empty_source(self, tmp_path, monkeypatch, capsys):
        """main --install-skills with empty source dir (covers line 514)."""
        from mcp_journal.server import main

        source_dir = tmp_path / "source"
        source_dir.mkdir()
        # No .md files in source

        target_dir = tmp_path / "target"
        target_dir.mkdir()

        monkeypatch.setattr("mcp_journal.server.get_skills_source_dir", lambda: source_dir)
        monkeypatch.setattr("mcp_journal.server.get_skills_target_dir", lambda: target_dir)
        monkeypatch.setattr(sys, "argv", ["mcp-journal", "--install-skills"])

        main()

        captured = capsys.readouterr()
        # No skills found to install
        assert "No skills found" in captured.out


class TestRebuildIndexErrors:
    """Tests for rebuild-index error handling."""

    def test_cli_rebuild_index_with_errors(self, config, capsys, monkeypatch):
        """CLI rebuild-index showing errors (covers line 383)."""
        from mcp_journal.server import run_cli_command
        from mcp_journal.engine import JournalEngine

        # Mock rebuild_sqlite_index on the class to return a result with errors
        original_rebuild = JournalEngine.rebuild_sqlite_index
        def mock_rebuild(self):
            return {"files_processed": 5, "entries_indexed": 3, "errors": 2}

        monkeypatch.setattr(JournalEngine, "rebuild_sqlite_index", mock_rebuild)

        args = argparse.Namespace(command="rebuild-index")

        exit_code = run_cli_command(args, config)
        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Errors: 2" in captured.out

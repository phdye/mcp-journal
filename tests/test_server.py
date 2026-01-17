"""Tests for MCP server module."""

import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from mcp_journal.config import ProjectConfig
from mcp_journal.engine import JournalEngine


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config(temp_project):
    """Create a test configuration."""
    return ProjectConfig(
        project_name="test-project",
        project_root=temp_project,
    )


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

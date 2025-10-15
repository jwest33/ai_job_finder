"""
MCP Server CLI Commands

Commands for managing the MCP server.
"""

import sys
import time
import subprocess
from pathlib import Path

import click

from src.cli.utils import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_key_value_table,
    confirm,
)


@click.group()
def mcp_group():
    """MCP server management commands"""
    pass


@mcp_group.command(name="start")
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=3000, type=int, help="Server port")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def start_server(host, port, reload):
    """Start the MCP server"""
    print_header("Starting MCP Server")

    print_section("Configuration")
    config = {
        "Host": host,
        "Port": port,
        "Reload": "Enabled" if reload else "Disabled",
    }
    print_key_value_table(config)

    try:
        import uvicorn
        from mcp_server.server import app
        from mcp_server.config import MCPServerConfig

        print_section("Server Info")
        print_info(f"  Name: {MCPServerConfig.NAME}")
        print_info(f"  Version: {MCPServerConfig.VERSION}")
        print_info(f"  Auth: {'Enabled' if MCPServerConfig.AUTH_ENABLED else 'Disabled'}")

        if MCPServerConfig.AUTH_ENABLED and not MCPServerConfig.AUTH_TOKEN:
            print_warning("\n⚠️  Authentication is enabled but no token is configured!")
            print_info("Generate a token with: python cli.py mcp generate-token")
            print()
            if not confirm("Continue anyway?"):
                return

        print_success(f"\n✓ Starting server at http://{host}:{port}")
        print_info("  Press Ctrl+C to stop")
        print()

        uvicorn.run(
            "mcp_server.server:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )

    except ImportError as e:
        print_error(f"Failed to import dependencies: {e}")
        print_info("\nInstall MCP dependencies with:")
        print_info("  pip install -r requirements.txt")
    except KeyboardInterrupt:
        print_info("\n\nServer stopped by user")
    except Exception as e:
        print_error(f"Failed to start server: {e}")
        raise


@mcp_group.command(name="test")
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=3000, type=int, help="Server port")
def test_server(host, port):
    """Test MCP server connection"""
    print_header("Testing MCP Server")

    import requests

    url = f"http://{host}:{port}"

    print_info(f"Testing connection to: {url}")

    try:
        # Test health endpoint
        response = requests.get(f"{url}/health", timeout=5)

        if response.status_code == 200:
            data = response.json()
            print_success("✓ Server is healthy")
            print_info(f"  Version: {data.get('version')}")
            print_info(f"  Status: {data.get('status')}")
        else:
            print_error(f"Health check failed: HTTP {response.status_code}")
            return

        # Test root endpoint
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            print_success("✓ Server info retrieved")

            print_section("Server Capabilities")
            capabilities = data.get("capabilities", {})
            print_info(f"  Tools: {', '.join(capabilities.get('tools', []))}")
            print_info(f"  Authentication: {'Enabled' if capabilities.get('authentication') else 'Disabled'}")
            print_info(f"  Rate Limiting: {'Enabled' if capabilities.get('rate_limiting') else 'Disabled'}")
        else:
            print_error(f"Failed to retrieve server info: HTTP {response.status_code}")

    except requests.exceptions.ConnectionError:
        print_error("❌ Connection failed - server is not running")
        print_info("\nStart the server with:")
        print_info("  python cli.py mcp start")
    except requests.exceptions.Timeout:
        print_error("❌ Connection timeout")
    except Exception as e:
        print_error(f"Test failed: {e}")


@mcp_group.command(name="generate-token")
def generate_token():
    """Generate a new authentication token"""
    print_header("Generate Authentication Token")

    try:
        from mcp_server.auth import MCPAuth

        token = MCPAuth.generate_token()

        print_success("✓ Token generated successfully")
        print()
        print_section("Your Token")
        print_info(f"  {token}")
        print()
        print_section("Next Steps")
        print_info("1. Add this token to your .env file:")
        print_info(f"   MCP_AUTH_TOKEN={token}")
        print()
        print_info("2. Restart the MCP server for changes to take effect")
        print()
        print_warning("⚠️  Keep this token secret! It provides full access to the MCP server.")

    except Exception as e:
        print_error(f"Failed to generate token: {e}")


@mcp_group.command(name="tools")
@click.option("--host", default="localhost", help="Server host")
@click.option("--port", default=3000, type=int, help="Server port")
def list_tools(host, port):
    """List all available tools"""
    print_header("MCP Server Tools")

    import requests

    url = f"http://{host}:{port}/tools"

    try:
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()

            if not data.get("success"):
                print_error("Failed to retrieve tools")
                return

            tools = data.get("data", {}).get("tools", [])

            # Group by category
            by_category = {}
            for tool in tools:
                category = tool["category"]
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(tool)

            for category, category_tools in sorted(by_category.items()):
                print_section(f"{category.replace('_', ' ').title()}")
                for tool in category_tools:
                    icon = "🔐" if tool["requires_auth"] else "🔓"
                    destructive = " ⚠️ " if tool["destructive"] else ""
                    accessible = "✓" if tool["accessible"] else "✗"
                    print_info(f"  {icon} {accessible} {tool['name']}{destructive}")

            print()
            print_success(f"Total tools: {len(tools)}")

        else:
            print_error(f"Failed to retrieve tools: HTTP {response.status_code}")

    except requests.exceptions.ConnectionError:
        print_error("❌ Connection failed - server is not running")
    except Exception as e:
        print_error(f"Failed to list tools: {e}")


@mcp_group.command(name="config")
def show_config():
    """Show MCP server configuration"""
    print_header("MCP Server Configuration")

    try:
        from mcp_server.config import MCPServerConfig

        print_section("Server Settings")
        server_config = {
            "Name": MCPServerConfig.NAME,
            "Version": MCPServerConfig.VERSION,
            "Host": MCPServerConfig.HOST,
            "Port": MCPServerConfig.PORT,
            "Log Level": MCPServerConfig.LOG_LEVEL,
        }
        print_key_value_table(server_config)

        print_section("Security Settings")
        security_config = {
            "Authentication": "Enabled" if MCPServerConfig.AUTH_ENABLED else "Disabled",
            "Token Configured": "Yes" if MCPServerConfig.AUTH_TOKEN else "No",
            "Rate Limiting": "Enabled" if MCPServerConfig.RATE_LIMIT_ENABLED else "Disabled",
        }
        print_key_value_table(security_config)

        print_section("Feature Flags")
        feature_config = {
            "Destructive Operations": "Allowed" if MCPServerConfig.ALLOW_DESTRUCTIVE_OPERATIONS else "Blocked",
            "Require Confirmation": "Yes" if MCPServerConfig.REQUIRE_CONFIRMATION else "No",
            "Audit Log": "Enabled" if MCPServerConfig.ENABLE_AUDIT_LOG else "Disabled",
        }
        print_key_value_table(feature_config)

    except Exception as e:
        print_error(f"Failed to load configuration: {e}")


@mcp_group.command(name="chat")
@click.option("--llama-url", default="http://localhost:8080", help="llama-server URL")
@click.option("--mcp-url", default="http://localhost:3000", help="MCP server URL")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def start_chat(llama_url, mcp_url, verbose):
    """Start interactive chat with local LLM"""
    from src.cli.mcp_chat import chat_command

    # Direct invocation - output goes to console
    chat_command.callback(llama_url=llama_url, mcp_url=mcp_url, verbose=verbose)


@mcp_group.command(name="chat-web")
@click.option("--port", default=5000, type=int, help="Web UI port")
@click.option("--host", default="localhost", help="Web UI host")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def start_web_chat(port, host, debug):
    """Start web-based MCP client with intelligent context management"""
    print_header("Starting MCP Web Client")

    try:
        from src.mcp_client.web.app import create_app

        print_section("Configuration")
        config = {
            "Host": host,
            "Port": port,
            "Debug": "Enabled" if debug else "Disabled",
        }
        print_key_value_table(config)

        print_section("Features")
        print_info("  • Natural language chat interface")
        print_info("  • Dynamic context management (knapsack algorithm)")
        print_info("  • Automatic conversation persistence")
        print_info("  • Token usage visualization")
        print_info("  • Tool call tracking")
        print()

        app = create_app()

        print_success(f"✓ Web UI starting at http://{host}:{port}")
        print_info("  Press Ctrl+C to stop")
        print()

        app.run(host=host, port=port, debug=debug)

    except ImportError as e:
        print_error(f"Failed to import dependencies: {e}")
        print_info("\nInstall web UI dependencies with:")
        print_info("  pip install -r requirements.txt")
    except KeyboardInterrupt:
        print_info("\n\nWeb UI stopped by user")
    except Exception as e:
        print_error(f"Failed to start web UI: {e}")
        if debug:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    mcp_group()

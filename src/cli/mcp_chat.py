"""
Interactive MCP Chat CLI

Terminal-based chat interface for the local MCP client.
"""

import sys
import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mcp_client.client import MCPClient
from src.mcp_client.conversation import ConversationManager
from src.cli.utils import print_header, print_error, print_success, print_info, print_warning

load_dotenv()

console = Console()


@click.command()
@click.option("--llama-url", default="http://localhost:8080", help="llama-server URL")
@click.option("--mcp-url", default="http://localhost:3000", help="MCP server URL")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def chat_command(llama_url, mcp_url, verbose):
    """Interactive chat with local LLM and MCP server"""

    # Get MCP token from env
    mcp_token = os.getenv("MCP_AUTH_TOKEN")

    # Initialize client
    print_header("Job Search AI Assistant (Local)")
    print_info("Initializing...")

    try:
        client = MCPClient(
            llama_url=llama_url,
            mcp_url=mcp_url,
            mcp_token=mcp_token,
        )

        conversation = ConversationManager()

        # Health check
        print_info("Checking services...")
        health = client.health_check()

        if not health["llama_server"]:
            print_error("[ERROR] llama-server not available")
            print_info(f"   Make sure it's running on {llama_url}")
            return

        if not health["mcp_server"]:
            print_error("[ERROR] MCP server not available")
            print_info(f"   Start it with: python cli.py mcp start")
            return

        print_success("[SUCCESS] All services online")
        print()

        # Check if there's a tool still running from previous session
        tool_status = conversation.get_tool_status()
        if tool_status:
            tool_name = tool_status.get("tool", "unknown")
            started = tool_status.get("started", "unknown time")
            print_warning(f"[WARNING] Tool '{tool_name}' was running at {started}")
            print_info("   It may have been interrupted. Consider retrying if needed.")
            print()

        # Show welcome message
        console.print(Panel.fit(
            "[bold cyan]Job Search AI Assistant[/bold cyan]\n\n"
            f"Model: Qwen3-30B (via llama-server)\n"
            f"MCP Server: {mcp_url}\n\n"
            "[dim]Type '/help' for commands, '/quit' to exit[/dim]",
            border_style="cyan",
        ))
        print()

        # Main chat loop
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("[bold green]You[/bold green]").strip()

                if not user_input:
                    continue

                # Handle special commands
                if user_input.startswith("/"):
                    if handle_command(user_input, client, conversation):
                        continue  # Command handled
                    else:
                        break  # Exit requested

                # Add to conversation
                conversation.add_message("user", user_input)

                # Dynamic status display with tool execution info
                current_status = "[bold yellow]Thinking...[/bold yellow]"

                def progress_callback(info):
                    """Update status display based on progress"""
                    nonlocal current_status
                    stage = info.get("stage")

                    if stage == "thinking":
                        current_status = "[bold yellow]Thinking...[/bold yellow]"
                        conversation.clear_tool_status()
                    elif stage == "tool_executing":
                        tool_name = info.get("tool", "unknown")
                        # Make tool name more readable
                        display_name = tool_name.replace("_", " ").replace(".", " → ")
                        current_status = f"[bold cyan][INFO] Running: {display_name}[/bold cyan]"
                        # Persist tool status for resume capability
                        conversation.set_tool_status(tool_name, "running")
                    elif stage == "tool_completed":
                        current_status = "[bold green][SUCCESS] Processing results...[/bold green]"
                        conversation.clear_tool_status()

                # Show thinking indicator with dynamic updates
                with console.status(current_status, spinner="dots") as status:
                    def status_update(info):
                        progress_callback(info)
                        status.update(current_status)

                    response = client.chat(user_input, verbose=verbose, progress_callback=status_update)

                # Add response to conversation
                conversation.add_message("assistant", response)

                # Display response
                console.print()
                console.print(Panel(
                    Markdown(response),
                    title="[bold cyan]Assistant[/bold cyan]",
                    border_style="cyan",
                ))
                console.print()

            except KeyboardInterrupt:
                print()
                if Prompt.ask("[yellow]Exit chat?[/yellow]", choices=["y", "n"], default="n") == "y":
                    break
            except Exception as e:
                print_error(f"Error: {e}")
                if verbose:
                    import traceback
                    traceback.print_exc()

    except Exception as e:
        print_error(f"Failed to initialize client: {e}")
        return

    # Goodbye
    print()
    print_success("Chat session ended. Goodbye!")


def handle_command(command: str, client: MCPClient, conversation: ConversationManager) -> bool:
    """
    Handle special commands

    Args:
        command: Command string
        client: MCP client
        conversation: Conversation manager

    Returns:
        True to continue chat, False to exit
    """
    parts = command[1:].split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "help":
        console.print(Panel(
            "[bold]Available Commands:[/bold]\n\n"
            "/help           - Show this help message\n"
            "/clear          - Clear conversation history\n"
            "/save [name]    - Save conversation\n"
            "/load <name>    - Load conversation\n"
            "/list           - List saved conversations\n"
            "/tools          - List available tools\n"
            "/stats          - Show conversation statistics\n"
            "/health         - Check service health\n"
            "/profile [name] - Show or switch profile\n"
            "/quit           - Exit chat",
            title="Help",
            border_style="yellow",
        ))
        return True

    elif cmd == "clear":
        conversation.clear()
        client.clear_conversation()
        print_success("[SUCCESS] Conversation cleared")
        return True

    elif cmd == "save":
        filename = args if args else None
        filepath = conversation.save(filename)
        print_success(f"[SUCCESS] Saved to: {filepath}")
        return True

    elif cmd == "load":
        if not args:
            print_error("Usage: /load <filename>")
            return True

        if conversation.load(args):
            # Also update client history
            client.messages = conversation.get_messages()
            print_success(f"[SUCCESS] Loaded: {args}")
        else:
            print_error(f"Failed to load: {args}")
        return True

    elif cmd == "list":
        conversations = conversation.list_saved_conversations()
        if conversations:
            console.print("\n[bold]Saved Conversations:[/bold]")
            for i, conv in enumerate(conversations[:10], 1):
                console.print(f"{i}. {conv.name}")
            if len(conversations) > 10:
                console.print(f"... and {len(conversations) - 10} more")
        else:
            print_info("No saved conversations")
        return True

    elif cmd == "tools":
        tools = client.list_tools()
        console.print(f"\n[bold]Available Tools:[/bold] ({len(tools)} total)\n")

        # Group by category
        by_category = {}
        for tool in tools:
            category = tool.split(".")[0]
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(tool)

        for category in sorted(by_category.keys()):
            console.print(f"[cyan]{category}:[/cyan]")
            for tool in sorted(by_category[category]):
                console.print(f"  • {tool}")
            console.print()

        return True

    elif cmd == "stats":
        stats = conversation.get_stats()
        console.print("\n[bold]Conversation Statistics:[/bold]\n")
        console.print(f"Messages: {stats['total_messages']}")
        console.print(f"  User: {stats['user_messages']}")
        console.print(f"  Assistant: {stats['assistant_messages']}")
        console.print(f"  Tool calls: {stats['tool_calls']}")
        console.print(f"Tokens: {stats['total_tokens']} / 8192 ({stats['token_usage_pct']:.1f}%)")
        console.print(f"Started: {stats['created_at']}")
        console.print()
        return True

    elif cmd == "health":
        health = client.health_check()
        console.print("\n[bold]Service Health:[/bold]\n")
        console.print(f"llama-server: {'[SUCCESS] Online' if health['llama_server'] else '[ERROR] Offline'}")
        console.print(f"MCP server: {'[SUCCESS] Online' if health['mcp_server'] else '[ERROR] Offline'}")
        console.print(f"Overall: {'[SUCCESS] All systems operational' if health['overall'] else '[ERROR] Issues detected'}")
        console.print()
        return True

    elif cmd == "profile":
        if args:
            # Switch profile via tool call
            print_info(f"Switching to profile: {args}")
            with console.status("[yellow]Switching...[/yellow]"):
                response = client.chat(f"Switch to profile {args}")
            console.print(Panel(response, title="Result", border_style="cyan"))
        else:
            # Show current profile
            current = conversation.get_profile()
            if current:
                print_info(f"Current profile: {current}")
            else:
                print_info("No profile set")
        return True

    elif cmd in ["quit", "exit", "q"]:
        # Ask to save
        if conversation.get_stats()["total_messages"] > 0:
            if Prompt.ask("[yellow]Save conversation before exiting?[/yellow]", choices=["y", "n"], default="n") == "y":
                conversation.save()
                print_success("[SUCCESS] Conversation saved")
        return False

    else:
        print_error(f"Unknown command: /{cmd}")
        print_info("Type /help for available commands")
        return True


if __name__ == "__main__":
    chat_command()

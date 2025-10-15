"""
CLI Utilities - Shared formatting and helper functions for the CLI

Provides consistent formatting, colors, prompts, and error handling across all CLI commands.
"""

import sys
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm, Prompt, IntPrompt
from rich.syntax import Syntax
from rich.tree import Tree
from rich import box
import questionary
from questionary import Style


# Console instance for all output
console = Console()

# Color scheme
COLORS = {
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "highlight": "magenta",
    "muted": "bright_black",
}

# Custom questionary style matching rich colors
QUESTIONARY_STYLE = Style([
    ("qmark", "fg:cyan bold"),
    ("question", "bold"),
    ("answer", "fg:green bold"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
    ("separator", "fg:#6c6c6c"),      # Gray color
    ("instruction", "fg:#6c6c6c"),    # Gray color
])


# =============================================================================
# Output Functions
# =============================================================================

def print_header(text: str, style: str = "bold cyan"):
    """Print a formatted header"""
    console.print(f"\n{text}", style=style)
    console.print("=" * len(text), style=style)


def print_section(text: str, style: str = "bold"):
    """Print a section header"""
    console.print(f"\n{text}", style=style)
    console.print("-" * len(text), style="bright_black")


def print_success(text: str):
    """Print success message"""
    console.print(f"[SUCCESS] {text}", style=f"{COLORS['success']}")


def print_error(text: str, exit_code: Optional[int] = None):
    """Print error message and optionally exit"""
    console.print(f"[ERROR] {text}", style=f"{COLORS['error']}")
    if exit_code is not None:
        sys.exit(exit_code)


def print_warning(text: str):
    """Print warning message"""
    console.print(f"[WARNING] {text}", style=f"{COLORS['warning']}")


def print_info(text: str):
    """Print info message"""
    console.print(f"[INFO] {text}", style=f"{COLORS['info']}")


def print_muted(text: str):
    """Print muted/dimmed text"""
    console.print(text, style=f"{COLORS['muted']}")


def print_panel(content: str, title: Optional[str] = None, style: str = "cyan"):
    """Print content in a panel"""
    console.print(Panel(content, title=title, border_style=style, box=box.ROUNDED))


def print_json(data: Dict[str, Any], title: Optional[str] = None):
    """Print JSON data with syntax highlighting"""
    import json
    json_str = json.dumps(data, indent=2)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    if title:
        console.print(f"\n[bold]{title}[/bold]")
    console.print(syntax)


# =============================================================================
# Table Functions
# =============================================================================

def create_table(
    title: str,
    columns: List[str],
    rows: List[List[Any]],
    show_header: bool = True,
    show_lines: bool = False,
) -> Table:
    """Create a rich table"""
    table = Table(
        title=title,
        show_header=show_header,
        show_lines=show_lines,
        box=box.ROUNDED,
        title_style="bold cyan",
    )

    for col in columns:
        table.add_column(col, style="cyan", no_wrap=False)

    for row in rows:
        table.add_row(*[str(cell) for cell in row])

    return table


def print_table(
    title: str,
    columns: List[str],
    rows: List[List[Any]],
    show_header: bool = True,
    show_lines: bool = False,
):
    """Print a formatted table"""
    table = create_table(title, columns, rows, show_header, show_lines)
    console.print(table)


def print_key_value_table(data: Dict[str, Any], title: Optional[str] = None):
    """Print key-value pairs as a table"""
    rows = [[key, value] for key, value in data.items()]
    print_table(
        title or "Configuration",
        columns=["Setting", "Value"],
        rows=rows,
        show_lines=False,
    )


# =============================================================================
# Progress Functions
# =============================================================================

def create_progress_bar() -> Progress:
    """Create a progress bar with spinner"""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def with_spinner(text: str, func: Callable, *args, **kwargs):
    """Execute function with a spinner"""
    with console.status(f"[cyan]{text}...", spinner="dots"):
        return func(*args, **kwargs)


# =============================================================================
# Prompt Functions
# =============================================================================

def confirm(question: str, default: bool = False) -> bool:
    """Ask for yes/no confirmation"""
    return questionary.confirm(
        question,
        default=default,
        style=QUESTIONARY_STYLE,
    ).ask()


def prompt_text(question: str, default: str = "") -> str:
    """Prompt for text input"""
    return questionary.text(
        question,
        default=default,
        style=QUESTIONARY_STYLE,
    ).ask()


def prompt_int(question: str, default: Optional[int] = None) -> int:
    """Prompt for integer input"""
    while True:
        result = questionary.text(
            question,
            default=str(default) if default is not None else "",
            style=QUESTIONARY_STYLE,
        ).ask()

        if result is None:
            sys.exit(0)

        try:
            return int(result)
        except ValueError:
            print_error("Please enter a valid number")


def prompt_choice(question: str, choices: List[str], default: Optional[str] = None) -> str:
    """Prompt for single choice from list"""
    return questionary.select(
        question,
        choices=choices,
        default=default,
        style=QUESTIONARY_STYLE,
    ).ask()


def prompt_checkbox(question: str, choices: List[str]) -> List[str]:
    """Prompt for multiple choices from list"""
    return questionary.checkbox(
        question,
        choices=choices,
        style=QUESTIONARY_STYLE,
    ).ask()


def prompt_path(question: str, default: str = "", must_exist: bool = False) -> Path:
    """Prompt for file/directory path"""
    while True:
        result = questionary.path(
            question,
            default=default,
            style=QUESTIONARY_STYLE,
        ).ask()

        if result is None:
            sys.exit(0)

        path = Path(result)

        if must_exist and not path.exists():
            print_error(f"Path does not exist: {path}")
            continue

        return path


# =============================================================================
# Validation Functions
# =============================================================================

def validate_file_exists(path: str) -> Path:
    """Validate that a file exists"""
    file_path = Path(path)
    if not file_path.exists():
        print_error(f"File not found: {path}", exit_code=1)
    if not file_path.is_file():
        print_error(f"Not a file: {path}", exit_code=1)
    return file_path


def validate_dir_exists(path: str) -> Path:
    """Validate that a directory exists"""
    dir_path = Path(path)
    if not dir_path.exists():
        print_error(f"Directory not found: {path}", exit_code=1)
    if not dir_path.is_dir():
        print_error(f"Not a directory: {path}", exit_code=1)
    return dir_path


def ensure_dir_exists(path: str) -> Path:
    """Ensure directory exists, create if needed"""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


# =============================================================================
# Tree Functions
# =============================================================================

def create_tree(label: str) -> Tree:
    """Create a tree structure for hierarchical display"""
    return Tree(f"[bold cyan]{label}[/bold cyan]")


def print_tree(tree: Tree):
    """Print a tree structure"""
    console.print(tree)


# =============================================================================
# Error Handling
# =============================================================================

def handle_error(error: Exception, verbose: bool = False):
    """Handle and display errors consistently"""
    print_error(f"Error: {str(error)}")

    if verbose:
        import traceback
        console.print("\n[dim]Traceback:[/dim]")
        console.print_exception()
    else:
        console.print("[dim]Use --verbose for full traceback[/dim]")


def exit_with_error(message: str, code: int = 1):
    """Print error and exit"""
    print_error(message)
    sys.exit(code)


# =============================================================================
# Formatting Helpers
# =============================================================================

def format_bytes(bytes_value: float) -> str:
    """Format bytes to human-readable size"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable duration"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_number(num: int) -> str:
    """Format number with thousand separators"""
    return f"{num:,}"


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


# =============================================================================
# CLI State Management
# =============================================================================

class CLIState:
    """Shared state for CLI commands"""

    def __init__(self):
        self.verbose = False
        self.quiet = False
        self.dry_run = False
        self.config_file = None

    def set_verbose(self, verbose: bool):
        self.verbose = verbose

    def set_quiet(self, quiet: bool):
        self.quiet = quiet

    def set_dry_run(self, dry_run: bool):
        self.dry_run = dry_run

    def set_config_file(self, config_file: Optional[str]):
        self.config_file = config_file

    def log(self, message: str, level: str = "info"):
        """Contextual logging based on state"""
        if self.quiet and level != "error":
            return

        if level == "debug" and not self.verbose:
            return

        if level == "info":
            print_info(message)
        elif level == "success":
            print_success(message)
        elif level == "warning":
            print_warning(message)
        elif level == "error":
            print_error(message)
        elif level == "debug":
            print_muted(f"[DEBUG] {message}")


# Global CLI state
cli_state = CLIState()

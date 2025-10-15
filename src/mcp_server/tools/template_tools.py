"""
Template Management Tools

Tools for managing resume and requirements templates.
"""

import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.profile_manager import ProfilePaths
from .base import template_registry, BaseTool
from ..utils.response_formatter import format_success_response


class TemplateListTool(BaseTool):
    """List current template files"""

    def __init__(self):
        super().__init__("list", "List current template files and their status")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        paths = ProfilePaths()

        templates = {
            "resume": {
                "path": str(paths.resume_path),
                "exists": paths.resume_path.exists(),
            },
            "requirements": {
                "path": str(paths.requirements_path),
                "exists": paths.requirements_path.exists(),
            },
        }

        # Get file stats if they exist
        if paths.resume_path.exists():
            stat = paths.resume_path.stat()
            templates["resume"]["size_bytes"] = stat.st_size
            templates["resume"]["modified"] = stat.st_mtime

        if paths.requirements_path.exists():
            stat = paths.requirements_path.stat()
            templates["requirements"]["size_bytes"] = stat.st_size
            templates["requirements"]["modified"] = stat.st_mtime

        return format_success_response({
            "templates": templates,
            "templates_directory": str(paths.templates_dir),
        })


class TemplateValidateTool(BaseTool):
    """Validate template files"""

    def __init__(self):
        super().__init__("validate", "Validate resume and requirements templates")

    async def execute(self, **kwargs) -> Dict[str, Any]:
        paths = ProfilePaths()
        validation_results = {}

        # Validate resume
        if not paths.resume_path.exists():
            validation_results["resume"] = {"valid": False, "error": "File does not exist"}
        else:
            try:
                with open(paths.resume_path, "r", encoding="utf-8") as f:
                    content = f.read()

                if not content.strip():
                    validation_results["resume"] = {"valid": False, "error": "File is empty"}
                else:
                    validation_results["resume"] = {
                        "valid": True,
                        "size_bytes": len(content),
                        "lines": len(content.split("\n")),
                    }
            except Exception as e:
                validation_results["resume"] = {"valid": False, "error": str(e)}

        # Validate requirements
        if not paths.requirements_path.exists():
            validation_results["requirements"] = {"valid": False, "error": "File does not exist"}
        else:
            try:
                import yaml

                with open(paths.requirements_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not data:
                    validation_results["requirements"] = {"valid": False, "error": "File is empty"}
                else:
                    validation_results["requirements"] = {
                        "valid": True,
                        "sections": list(data.keys()),
                    }
            except Exception as e:
                validation_results["requirements"] = {"valid": False, "error": str(e)}

        all_valid = all(r.get("valid", False) for r in validation_results.values())

        return format_success_response({
            "validation_results": validation_results,
            "all_valid": all_valid,
        })


# Register tools
template_registry.register("list", TemplateListTool())
template_registry.register("validate", TemplateValidateTool())


async def execute(tool_action: str, parameters: Dict[str, Any]) -> Any:
    """Execute a template tool"""
    tool = template_registry.get(tool_action)
    if not tool:
        raise ValueError(f"Unknown template tool: {tool_action}")
    return await tool.execute(**parameters)

"""
Conversation Manager

Handles conversation history, persistence, and context window management.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manager for conversation history and persistence"""

    def __init__(
        self,
        max_tokens: int = 8192,
        conversations_dir: str = "conversations",
    ):
        """
        Initialize conversation manager

        Args:
            max_tokens: Maximum context window size
            conversations_dir: Directory to store conversations
        """
        self.max_tokens = max_tokens
        self.conversations_dir = Path(conversations_dir)
        self.conversations_dir.mkdir(exist_ok=True)

        self.current_conversation: Dict[str, Any] = {
            "messages": [],
            "total_tokens": 0,
            "created_at": datetime.now().isoformat(),
            "profile": None,
            "current_tool": None,  # Track currently executing tool
        }

    def add_message(
        self,
        role: str,
        content: str,
        name: Optional[str] = None,
        tokens: Optional[int] = None,
    ):
        """
        Add message to conversation

        Args:
            role: Message role (user, assistant, tool, system)
            content: Message content
            name: Tool name (for tool messages)
            tokens: Token count (estimated if not provided)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

        if name:
            message["name"] = name

        # Estimate tokens if not provided
        if tokens is None:
            tokens = len(content) // 4  # Rough approximation

        message["tokens"] = tokens

        self.current_conversation["messages"].append(message)
        self.current_conversation["total_tokens"] += tokens

        # Check if we're approaching context limit
        if self.current_conversation["total_tokens"] > self.max_tokens * 0.8:
            logger.warning("Approaching context window limit, consider summarizing")

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Get all messages in current conversation

        Returns:
            List of messages
        """
        return self.current_conversation["messages"].copy()

    def get_recent_messages(self, count: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent messages

        Args:
            count: Number of recent messages to return

        Returns:
            List of recent messages
        """
        messages = self.current_conversation["messages"]
        return messages[-count:] if len(messages) > count else messages

    def clear(self):
        """Clear current conversation"""
        self.current_conversation = {
            "messages": [],
            "total_tokens": 0,
            "created_at": datetime.now().isoformat(),
            "profile": self.current_conversation.get("profile"),
        }

    def save(self, filename: Optional[str] = None) -> Path:
        """
        Save conversation to file

        Args:
            filename: Filename (auto-generated if not provided)

        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{timestamp}.json"

        filepath = self.conversations_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.current_conversation, f, indent=2)

        logger.info(f"Conversation saved to: {filepath}")
        return filepath

    def load(self, filename: str) -> bool:
        """
        Load conversation from file

        Args:
            filename: Filename or path to load

        Returns:
            True if loaded successfully
        """
        filepath = Path(filename)

        if not filepath.is_absolute():
            filepath = self.conversations_dir / filepath

        if not filepath.exists():
            logger.error(f"Conversation file not found: {filepath}")
            return False

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.current_conversation = json.load(f)

            logger.info(f"Conversation loaded from: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            return False

    def list_saved_conversations(self) -> List[Path]:
        """
        List all saved conversations

        Returns:
            List of conversation file paths
        """
        return sorted(
            self.conversations_dir.glob("conversation_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get conversation statistics

        Returns:
            Dict with conversation stats
        """
        messages = self.current_conversation["messages"]

        return {
            "total_messages": len(messages),
            "total_tokens": self.current_conversation["total_tokens"],
            "token_usage_pct": (self.current_conversation["total_tokens"] / self.max_tokens) * 100,
            "user_messages": sum(1 for m in messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in messages if m["role"] == "assistant"),
            "tool_calls": sum(1 for m in messages if m["role"] == "tool"),
            "created_at": self.current_conversation["created_at"],
        }

    def summarize_old_messages(self, keep_recent: int = 5) -> str:
        """
        Summarize old messages to reduce context

        Args:
            keep_recent: Number of recent messages to keep unchanged

        Returns:
            Summary text
        """
        messages = self.current_conversation["messages"]

        if len(messages) <= keep_recent:
            return ""

        # Messages to summarize
        old_messages = messages[:-keep_recent]

        # Create summary
        summary_parts = []
        for msg in old_messages:
            role = msg["role"]
            content = msg["content"][:100]  # First 100 chars
            summary_parts.append(f"{role}: {content}...")

        summary = "Previous conversation summary:\n" + "\n".join(summary_parts)

        # Update conversation with summary
        self.current_conversation["messages"] = [
            {"role": "system", "content": summary, "timestamp": datetime.now().isoformat()}
        ] + messages[-keep_recent:]

        # Recalculate tokens
        self.current_conversation["total_tokens"] = sum(
            m.get("tokens", len(m["content"]) // 4)
            for m in self.current_conversation["messages"]
        )

        return summary

    def set_profile(self, profile_name: str):
        """
        Set current profile context

        Args:
            profile_name: Profile name
        """
        self.current_conversation["profile"] = profile_name

    def get_profile(self) -> Optional[str]:
        """
        Get current profile

        Returns:
            Profile name or None
        """
        return self.current_conversation.get("profile")

    def set_tool_status(self, tool_name: str, status: str):
        """
        Record currently executing tool

        Args:
            tool_name: Name of the tool being executed
            status: Status (running, completed, failed)
        """
        self.current_conversation["current_tool"] = {
            "tool": tool_name,
            "status": status,
            "started": datetime.now().isoformat(),
        }
        # Auto-save to persist status
        self.save("current_conversation.json")

    def get_tool_status(self) -> Optional[Dict[str, Any]]:
        """
        Get currently executing tool status

        Returns:
            Dict with tool info or None if no tool running
        """
        return self.current_conversation.get("current_tool")

    def clear_tool_status(self):
        """Clear tool status when execution completes"""
        self.current_conversation["current_tool"] = None
        # Auto-save to persist cleared status
        self.save("current_conversation.json")

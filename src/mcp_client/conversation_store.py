"""
Enhanced Conversation Store

Manages conversation persistence with automatic archiving and pointer system.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConversationMetadata:
    """Metadata for a conversation"""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    total_tokens: int
    archived_count: int
    profile: Optional[str] = None


class EnhancedConversationStore:
    """
    Enhanced conversation storage with archiving support

    Stores conversations with intelligent archiving:
    - Active conversations in conversations/active/
    - Archived conversations in conversations/archives/YYYY-MM/
    - External data in conversations/data/
    """

    def __init__(
        self,
        base_dir: str = "conversations"
    ):
        """
        Initialize conversation store

        Args:
            base_dir: Base directory for conversation storage
        """
        self.base_dir = Path(base_dir)
        self.active_dir = self.base_dir / "active"
        self.archive_dir = self.base_dir / "archives"
        self.data_dir = self.base_dir / "data"

        # Create directories
        self.active_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Conversation store initialized at: {self.base_dir}")

    def create_conversation(
        self,
        title: Optional[str] = None,
        profile: Optional[str] = None
    ) -> str:
        """
        Create a new conversation

        Args:
            title: Conversation title (auto-generated if not provided)
            profile: Associated profile name

        Returns:
            Conversation ID
        """
        conv_id = self._generate_conversation_id()

        if title is None:
            title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        conversation = {
            'id': conv_id,
            'title': title,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'profile': profile,
            'messages': [],
            'pointers': [],
            'excluded_messages': [],  # Indices of messages excluded from context
            'context_stats': {
                'total_tokens': 0,
                'message_count': 0,
                'archived_count': 0,
            }
        }

        self._save_conversation(conv_id, conversation)

        logger.info(f"Created conversation: {conv_id}")
        return conv_id

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        tokens: Optional[int] = None,
        name: Optional[str] = None
    ):
        """
        Add message to conversation

        Args:
            conv_id: Conversation ID
            role: Message role
            content: Message content
            tokens: Token count
            name: Tool name (for tool messages)
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            raise ValueError(f"Conversation not found: {conv_id}")

        # Estimate tokens if not provided
        if tokens is None:
            tokens = len(content) // 4

        message = {
            'role': role,
            'content': content,
            'tokens': tokens,
            'timestamp': datetime.now().isoformat(),
        }

        if name:
            message['name'] = name

        conversation['messages'].append(message)
        conversation['updated_at'] = datetime.now().isoformat()
        conversation['context_stats']['total_tokens'] += tokens
        conversation['context_stats']['message_count'] = len(conversation['messages'])

        self._save_conversation(conv_id, conversation)

    def update_context(
        self,
        conv_id: str,
        messages: List[Dict[str, Any]],
        pointers: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ):
        """
        Update conversation with optimized context

        Args:
            conv_id: Conversation ID
            messages: Optimized message list
            pointers: Archived message pointers
            stats: Context statistics
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            raise ValueError(f"Conversation not found: {conv_id}")

        # Preserve actual message count (total messages, not just active/optimized)
        actual_message_count = len(conversation['messages'])

        conversation['messages'] = messages
        conversation['pointers'] = pointers
        conversation['context_stats'] = stats
        conversation['context_stats']['message_count'] = actual_message_count
        conversation['updated_at'] = datetime.now().isoformat()

        self._save_conversation(conv_id, conversation)

    def load_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """
        Load conversation by ID

        Args:
            conv_id: Conversation ID

        Returns:
            Conversation dict or None if not found
        """
        # Try active conversations first
        filepath = self.active_dir / f"{conv_id}.json"

        if not filepath.exists():
            # Try archives
            filepath = self._find_in_archives(conv_id)

        if filepath and filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
                logger.debug(f"Loaded conversation: {conv_id}")
                return conversation
            except Exception as e:
                logger.error(f"Failed to load conversation {conv_id}: {e}")
                return None

        logger.warning(f"Conversation not found: {conv_id}")
        return None

    def list_conversations(
        self,
        limit: Optional[int] = None,
        profile: Optional[str] = None
    ) -> List[ConversationMetadata]:
        """
        List all conversations

        Args:
            limit: Maximum number to return
            profile: Filter by profile

        Returns:
            List of conversation metadata
        """
        conversations = []

        # Get active conversations
        for filepath in self.active_dir.glob("*.json"):
            metadata = self._load_metadata(filepath)
            if metadata and (profile is None or metadata.profile == profile):
                conversations.append(metadata)

        # Sort by updated_at (most recent first)
        conversations.sort(key=lambda x: x.updated_at, reverse=True)

        if limit:
            conversations = conversations[:limit]

        return conversations

    def archive_conversation(self, conv_id: str):
        """
        Move conversation to archives

        Args:
            conv_id: Conversation ID
        """
        active_path = self.active_dir / f"{conv_id}.json"

        if not active_path.exists():
            logger.warning(f"Conversation not in active folder: {conv_id}")
            return

        try:
            conversation = self.load_conversation(conv_id)
            created_date = datetime.fromisoformat(conversation['created_at'])

            # Create archive directory for year-month
            archive_month_dir = self.archive_dir / created_date.strftime("%Y-%m")
            archive_month_dir.mkdir(parents=True, exist_ok=True)

            # Move to archive
            archive_path = archive_month_dir / f"{conv_id}.json"
            active_path.rename(archive_path)

            logger.info(f"Archived conversation: {conv_id}")
        except Exception as e:
            logger.error(f"Failed to archive conversation {conv_id}: {e}")

    def delete_conversation(self, conv_id: str):
        """
        Delete conversation permanently

        Args:
            conv_id: Conversation ID
        """
        # Try active folder
        filepath = self.active_dir / f"{conv_id}.json"

        if not filepath.exists():
            # Try archives
            filepath = self._find_in_archives(conv_id)

        if filepath and filepath.exists():
            try:
                filepath.unlink()
                logger.info(f"Deleted conversation: {conv_id}")
            except Exception as e:
                logger.error(f"Failed to delete conversation {conv_id}: {e}")
        else:
            logger.warning(f"Conversation not found: {conv_id}")

    def get_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        """
        Get all messages for a conversation

        Args:
            conv_id: Conversation ID

        Returns:
            List of messages
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            return []

        return conversation.get('messages', [])

    def get_pointers(self, conv_id: str) -> List[Dict[str, Any]]:
        """
        Get archived message pointers

        Args:
            conv_id: Conversation ID

        Returns:
            List of pointers
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            return []

        return conversation.get('pointers', [])

    def update_title(self, conv_id: str, title: str):
        """
        Update conversation title

        Args:
            conv_id: Conversation ID
            title: New title
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            raise ValueError(f"Conversation not found: {conv_id}")

        conversation['title'] = title
        conversation['updated_at'] = datetime.now().isoformat()

        self._save_conversation(conv_id, conversation)

    def exclude_message_from_context(self, conv_id: str, message_index: int):
        """
        Exclude a message from context optimization

        Args:
            conv_id: Conversation ID
            message_index: Index of message to exclude
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            raise ValueError(f"Conversation not found: {conv_id}")

        excluded = conversation.get('excluded_messages', [])
        if message_index not in excluded:
            excluded.append(message_index)
            conversation['excluded_messages'] = excluded
            conversation['updated_at'] = datetime.now().isoformat()

            self._save_conversation(conv_id, conversation)
            logger.info(f"Message {message_index} excluded from context in {conv_id}")

    def restore_message_to_context(self, conv_id: str, message_index: int):
        """
        Restore a previously excluded message to context

        Args:
            conv_id: Conversation ID
            message_index: Index of message to restore
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            raise ValueError(f"Conversation not found: {conv_id}")

        excluded = conversation.get('excluded_messages', [])
        if message_index in excluded:
            excluded.remove(message_index)
            conversation['excluded_messages'] = excluded
            conversation['updated_at'] = datetime.now().isoformat()

            self._save_conversation(conv_id, conversation)
            logger.info(f"Message {message_index} restored to context in {conv_id}")

    def get_excluded_messages(self, conv_id: str) -> List[int]:
        """
        Get list of excluded message indices

        Args:
            conv_id: Conversation ID

        Returns:
            List of excluded message indices
        """
        conversation = self.load_conversation(conv_id)

        if conversation is None:
            return []

        return conversation.get('excluded_messages', [])

    def _save_conversation(self, conv_id: str, conversation: Dict[str, Any]):
        """
        Save conversation to file

        Args:
            conv_id: Conversation ID
            conversation: Conversation dict
        """
        filepath = self.active_dir / f"{conv_id}.json"

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, indent=2)
            logger.debug(f"Saved conversation: {conv_id}")
        except Exception as e:
            logger.error(f"Failed to save conversation {conv_id}: {e}")

    def _generate_conversation_id(self) -> str:
        """
        Generate unique conversation ID

        Returns:
            Unique ID string
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"conv_{timestamp}"

    def _find_in_archives(self, conv_id: str) -> Optional[Path]:
        """
        Find conversation in archives

        Args:
            conv_id: Conversation ID

        Returns:
            Path to conversation file or None
        """
        for archive_month in self.archive_dir.iterdir():
            if archive_month.is_dir():
                filepath = archive_month / f"{conv_id}.json"
                if filepath.exists():
                    return filepath

        return None

    def _load_metadata(self, filepath: Path) -> Optional[ConversationMetadata]:
        """
        Load conversation metadata without full conversation

        Args:
            filepath: Path to conversation file

        Returns:
            ConversationMetadata or None
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = ConversationMetadata(
                id=data['id'],
                title=data.get('title', 'Untitled'),
                created_at=data['created_at'],
                updated_at=data.get('updated_at', data['created_at']),
                message_count=data.get('context_stats', {}).get('message_count', 0),
                total_tokens=data.get('context_stats', {}).get('total_tokens', 0),
                archived_count=data.get('context_stats', {}).get('archived_count', 0),
                profile=data.get('profile'),
            )

            return metadata
        except Exception as e:
            logger.error(f"Failed to load metadata from {filepath}: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about conversation store

        Returns:
            Statistics dictionary
        """
        active_count = len(list(self.active_dir.glob("*.json")))

        archive_count = 0
        for archive_month in self.archive_dir.iterdir():
            if archive_month.is_dir():
                archive_count += len(list(archive_month.glob("*.json")))

        return {
            'active_conversations': active_count,
            'archived_conversations': archive_count,
            'total_conversations': active_count + archive_count,
        }

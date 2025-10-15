"""
Dynamic Context Manager

Implements intelligent context window management using dynamic programming
to optimize which messages/data to include in the LLM's context window.
"""

import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DynamicContextManager:
    """
    Manages context window optimization using knapsack algorithm

    Allocates tokens optimally across:
    - System prompt (fixed)
    - Tool schemas (fixed)
    - Recent conversation history (dynamic)
    - Tool results (high priority)
    - Archived message pointers (compressed)
    """

    def __init__(
        self,
        max_tokens: int = 8192,
        data_dir: str = "conversations/data"
    ):
        """
        Initialize context manager

        Args:
            max_tokens: Maximum context window size
            data_dir: Directory for external data storage
        """
        self.max_tokens = max_tokens
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Token budget allocation
        self.reserved_tokens = {
            'system_prompt': 1000,
            'tool_schemas': 2000,
            'current_query': 500,
            'buffer': 300,  # Safety buffer
        }

        self.available_for_history = max_tokens - sum(self.reserved_tokens.values())

        logger.info(f"Context manager initialized: {self.available_for_history} tokens available for history")

    def optimize_context(
        self,
        messages: List[Dict[str, Any]],
        current_query: str,
        current_query_tokens: int,
        excluded_indices: Optional[List[int]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Optimize context using knapsack algorithm

        Args:
            messages: All conversation messages
            current_query: Current user query
            current_query_tokens: Token count for current query
            excluded_indices: List of message indices to exclude from context

        Returns:
            Tuple of (messages_to_include, pointers, stats)
        """
        if not messages:
            return [], [], {'total_tokens': 0, 'archived_count': 0}

        # Adjust available capacity based on current query size
        capacity = self.available_for_history - current_query_tokens

        if capacity <= 0:
            logger.warning("Current query too large, no room for history")
            return [], [], {'total_tokens': current_query_tokens, 'archived_count': len(messages)}

        # Prepare items for knapsack, filtering out excluded messages
        items = self._prepare_items(messages, excluded_indices or [])

        # Run knapsack algorithm
        selected_indices = self._knapsack_dp(items, capacity)

        # Separate selected and excluded messages
        selected_messages = [items[i]['message'] for i in selected_indices]
        excluded_messages = [items[i] for i in range(len(items)) if i not in selected_indices]

        # Create pointers for excluded messages
        pointers = self._create_pointers(excluded_messages)

        # Calculate statistics
        stats = {
            'total_tokens': sum(msg.get('tokens', 0) for msg in selected_messages) + current_query_tokens,
            'available_tokens': self.max_tokens - sum(self.reserved_tokens.values()),
            'message_count': len(selected_messages),
            'archived_count': len(excluded_messages),
            'capacity_used': sum(msg.get('tokens', 0) for msg in selected_messages),
            'capacity_available': capacity
        }

        logger.info(f"Context optimized: {stats['message_count']} messages, "
                   f"{stats['total_tokens']} total tokens, "
                   f"{stats['archived_count']} archived")

        return selected_messages, pointers, stats

    def _prepare_items(self, messages: List[Dict[str, Any]], excluded_indices: List[int]) -> List[Dict[str, Any]]:
        """
        Prepare messages as items for knapsack algorithm

        Args:
            messages: List of conversation messages
            excluded_indices: Indices of messages to exclude from context

        Returns:
            List of items with value, weight, and metadata
        """
        items = []
        total = len(messages)
        excluded_set = set(excluded_indices)

        for i, msg in enumerate(messages):
            # Skip excluded messages
            if i in excluded_set:
                continue

            # Estimate tokens if not provided
            tokens = msg.get('tokens')
            if tokens is None:
                tokens = len(msg.get('content', '')) // 4
                msg['tokens'] = tokens

            # Calculate value based on multiple factors
            value = self._calculate_value(msg, i, total)

            items.append({
                'index': i,
                'message': msg,
                'value': value,
                'weight': tokens,
            })

        return items

    def _calculate_value(
        self,
        msg: Dict[str, Any],
        index: int,
        total: int
    ) -> float:
        """
        Calculate message value/importance

        Value is based on:
        - Recency (newer = higher value)
        - Role (tool results > user > assistant)
        - Content type (errors, important state changes)

        Args:
            msg: Message dict
            index: Message index in conversation
            total: Total number of messages

        Returns:
            Value score (higher = more important)
        """
        # Base recency score (0-100)
        # Recent messages get exponentially higher scores
        recency_ratio = index / max(total - 1, 1)
        recency_score = 50 * (recency_ratio ** 2) + 50  # Range: 50-100

        # Role-based multipliers
        role_multipliers = {
            'tool': 2.5,      # Tool results are very important
            'user': 2.0,      # User questions/requests
            'assistant': 1.0, # Regular responses
            'system': 1.5,    # System messages (errors, state)
        }

        role = msg.get('role', 'assistant')
        multiplier = role_multipliers.get(role, 1.0)

        # Content-based bonuses
        content = msg.get('content', '').lower()
        bonus = 0

        if 'error' in content or 'failed' in content:
            bonus += 20  # Errors are important context

        if msg.get('name'):  # Tool name present
            bonus += 15

        # Final value calculation
        value = (recency_score * multiplier) + bonus

        return value

    def _knapsack_dp(
        self,
        items: List[Dict[str, Any]],
        capacity: int
    ) -> List[int]:
        """
        Solve 0/1 knapsack problem using dynamic programming

        Args:
            items: List of items with 'value' and 'weight'
            capacity: Maximum weight capacity

        Returns:
            List of selected item indices
        """
        n = len(items)

        if n == 0 or capacity <= 0:
            return []

        # DP table: dp[i][w] = max value using first i items with weight limit w
        # Use space-optimized version with just current and previous row
        dp = [[0] * (capacity + 1) for _ in range(2)]

        # Fill DP table
        for i in range(1, n + 1):
            item = items[i - 1]
            weight = int(item['weight'])
            value = item['value']

            current_row = i % 2
            prev_row = (i - 1) % 2

            for w in range(capacity + 1):
                # Don't include item
                dp[current_row][w] = dp[prev_row][w]

                # Include item if it fits
                if weight <= w:
                    include_value = dp[prev_row][w - weight] + value
                    dp[current_row][w] = max(dp[current_row][w], include_value)

        # Backtrack to find selected items
        selected = []
        w = capacity

        # Rebuild full DP table for backtracking (needed for accurate reconstruction)
        dp_full = [[0] * (capacity + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            item = items[i - 1]
            weight = int(item['weight'])
            value = item['value']

            for w_idx in range(capacity + 1):
                dp_full[i][w_idx] = dp_full[i - 1][w_idx]
                if weight <= w_idx:
                    include_value = dp_full[i - 1][w_idx - weight] + value
                    dp_full[i][w_idx] = max(dp_full[i][w_idx], include_value)

        # Backtrack
        for i in range(n, 0, -1):
            if dp_full[i][w] != dp_full[i - 1][w]:
                selected.append(i - 1)
                w -= int(items[i - 1]['weight'])

        selected.reverse()
        return selected

    def _create_pointers(
        self,
        excluded_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create compact pointers for excluded messages

        Args:
            excluded_items: Items not included in context

        Returns:
            List of pointer objects with summaries
        """
        if not excluded_items:
            return []

        # Sort by index
        excluded_items.sort(key=lambda x: x['index'])

        # Group consecutive messages
        groups = self._group_consecutive(excluded_items)

        pointers = []
        for group in groups:
            pointer = self._create_group_pointer(group)
            pointers.append(pointer)

        return pointers

    def _group_consecutive(
        self,
        items: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Group consecutive items together

        Args:
            items: Sorted list of items by index

        Returns:
            List of groups (each group is a list of consecutive items)
        """
        if not items:
            return []

        groups = []
        current_group = [items[0]]

        for item in items[1:]:
            if item['index'] == current_group[-1]['index'] + 1:
                current_group.append(item)
            else:
                groups.append(current_group)
                current_group = [item]

        groups.append(current_group)
        return groups

    def _create_group_pointer(
        self,
        group: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create pointer for a group of messages

        Args:
            group: Group of consecutive messages

        Returns:
            Pointer dict with summary and metadata
        """
        start_idx = group[0]['index']
        end_idx = group[-1]['index']

        # Generate summary
        summary = self._summarize_group(group)

        # Save full data externally if group is large
        storage_key = None
        if len(group) > 3:
            storage_key = f"archived_messages_{start_idx}_{end_idx}.json"
            self._save_archived_data(storage_key, [item['message'] for item in group])

        pointer = {
            'type': 'archived_messages',
            'range': f"{start_idx}-{end_idx}",
            'count': len(group),
            'summary': summary,
            'token_count': sum(item['weight'] for item in group),
            'storage_key': storage_key,
            'archived_at': datetime.now().isoformat(),
        }

        return pointer

    def _summarize_group(self, group: List[Dict[str, Any]]) -> str:
        """
        Create summary for a group of messages

        Args:
            group: List of message items

        Returns:
            Human-readable summary string
        """
        if not group:
            return "Empty group"

        # Analyze group composition
        roles = [item['message'].get('role', 'unknown') for item in group]
        role_counts = {}
        for role in roles:
            role_counts[role] = role_counts.get(role, 0) + 1

        # Check for tool calls
        tool_names = [
            item['message'].get('name')
            for item in group
            if item['message'].get('role') == 'tool'
        ]

        # Build summary
        parts = []

        if role_counts.get('user', 0) > 0:
            parts.append(f"{role_counts['user']} user message(s)")

        if role_counts.get('assistant', 0) > 0:
            parts.append(f"{role_counts['assistant']} response(s)")

        if tool_names:
            unique_tools = set(tool_names)
            parts.append(f"tool calls: {', '.join(unique_tools)}")

        summary = ", ".join(parts) if parts else f"{len(group)} message(s)"

        return f"Messages #{group[0]['index']}-{group[-1]['index']}: {summary}"

    def _save_archived_data(
        self,
        key: str,
        data: List[Dict[str, Any]]
    ):
        """
        Save archived data to external storage

        Args:
            key: Storage key/filename
            data: Data to save
        """
        filepath = self.data_dir / key

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Archived data saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save archived data {key}: {e}")

    def load_archived_data(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load archived data from external storage

        Args:
            key: Storage key/filename

        Returns:
            Loaded data or None if not found
        """
        filepath = self.data_dir / key

        if not filepath.exists():
            logger.warning(f"Archived data not found: {key}")
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Archived data loaded: {filepath}")
            return data
        except Exception as e:
            logger.error(f"Failed to load archived data {key}: {e}")
            return None

    def get_context_stats(
        self,
        messages: List[Dict[str, Any]],
        pointers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get statistics about current context usage

        Args:
            messages: Current messages in context
            pointers: Archived message pointers

        Returns:
            Stats dictionary
        """
        total_tokens = sum(msg.get('tokens', 0) for msg in messages)
        archived_tokens = sum(p.get('token_count', 0) for p in pointers)

        return {
            'total_tokens': total_tokens,
            'max_tokens': self.max_tokens,
            'usage_percent': (total_tokens / self.max_tokens) * 100,
            'available_tokens': self.max_tokens - total_tokens,
            'message_count': len(messages),
            'archived_count': sum(p.get('count', 0) for p in pointers),
            'archived_tokens': archived_tokens,
            'pointer_count': len(pointers),
            'health': self._assess_context_health(total_tokens),
        }

    def _assess_context_health(self, current_tokens: int) -> str:
        """
        Assess context window health

        Args:
            current_tokens: Current token usage

        Returns:
            Health status: 'healthy', 'warning', 'critical'
        """
        usage_percent = (current_tokens / self.max_tokens) * 100

        if usage_percent < 60:
            return 'healthy'
        elif usage_percent < 85:
            return 'warning'
        else:
            return 'critical'

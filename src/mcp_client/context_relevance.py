"""
Context Relevance Analyzer

Determines whether a user message needs full conversation context or can be
processed standalone. This reduces token usage and prevents LLM confusion.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ContextRelevanceAnalyzer:
    """Analyzes whether messages need conversation context"""

    def __init__(self, llama_url: str):
        """
        Initialize the context relevance analyzer

        Args:
            llama_url: llama-server URL for analysis
        """
        self.llama_url = llama_url

    def analyze_message(
        self,
        message: str,
        conversation_history: List[Dict[str, Any]],
        max_history: int = 10,
    ) -> Dict[str, Any]:
        """
        Analyze if a message needs conversation context

        Args:
            message: User's current message
            conversation_history: Full conversation history
            max_history: Maximum history messages to consider

        Returns:
            Dict with:
                - needs_context: bool
                - reason: str
                - relevant_messages: List[int] (indices of relevant messages)
                - confidence: float (0-1)
        """
        # Quick heuristic checks (no LLM needed)
        heuristic_result = self._heuristic_check(message)

        if heuristic_result["confidence"] > 0.8:
            return heuristic_result

        # Use LLM for nuanced analysis
        return self._llm_analysis(message, conversation_history, max_history)

    def _heuristic_check(self, message: str) -> Dict[str, Any]:
        """
        Fast heuristic check for obvious cases

        Args:
            message: User message

        Returns:
            Analysis result
        """
        message_lower = message.lower().strip()

        # Standalone indicators (high confidence)
        standalone_indicators = [
            # Commands and requests
            "list", "show", "get", "fetch", "display",
            "create", "delete", "update", "search",
            # Tool names
            "profile", "scraper", "matcher", "tracker",
            # Specific questions
            "what is", "how do i", "can you",
            "tell me about", "explain",
        ]

        # Context indicators (high confidence)
        context_indicators = [
            # References to previous messages
            "that", "this", "it", "them", "those", "these",
            "the one", "from before", "earlier", "previous",
            "you said", "you mentioned", "as you",
            # Follow-up questions
            "why", "how about", "what about",
            "also", "additionally", "furthermore",
            # Corrections/clarifications
            "no,", "actually", "i meant", "instead",
            "not that", "rather", "correction",
        ]

        # Check for standalone indicators
        if any(indicator in message_lower for indicator in standalone_indicators):
            # But also check if context indicators override
            if any(indicator in message_lower for indicator in context_indicators):
                return {
                    "needs_context": True,
                    "reason": "Contains both standalone and context indicators",
                    "relevant_messages": [],  # Will be determined by LLM
                    "confidence": 0.6,
                }

            return {
                "needs_context": False,
                "reason": "Standalone command/question detected",
                "relevant_messages": [],
                "confidence": 0.85,
            }

        # Check for context indicators
        if any(indicator in message_lower for indicator in context_indicators):
            return {
                "needs_context": True,
                "reason": "Contains references to previous context",
                "relevant_messages": [],  # Will be determined later
                "confidence": 0.85,
            }

        # Very short messages often need context
        if len(message.split()) <= 3:
            return {
                "needs_context": True,
                "reason": "Very short message, likely needs context",
                "relevant_messages": [],
                "confidence": 0.7,
            }

        # Default: standalone with moderate confidence
        return {
            "needs_context": False,
            "reason": "No clear context indicators",
            "relevant_messages": [],
            "confidence": 0.6,
        }

    def _llm_analysis(
        self,
        message: str,
        conversation_history: List[Dict[str, Any]],
        max_history: int,
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze context needs

        Args:
            message: User message
            conversation_history: Conversation history
            max_history: Max history to analyze

        Returns:
            Analysis result
        """
        import requests
        import json

        # Get recent history for context
        recent_history = conversation_history[-max_history:] if conversation_history else []

        # Format history for LLM
        history_text = "\n".join([
            f"{i+1}. {msg['role'].upper()}: {msg['content'][:100]}..."
            for i, msg in enumerate(recent_history)
        ])

        # Analysis prompt
        prompt = f"""Analyze whether the following user message needs the conversation history to be understood and answered correctly.

CONVERSATION HISTORY:
{history_text if history_text else "(No previous messages)"}

CURRENT USER MESSAGE:
"{message}"

Determine:
1. Does this message reference or depend on information from the conversation history?
2. Can it be understood and answered as a standalone message?

Respond with a JSON object:
{{
    "needs_context": true/false,
    "reason": "brief explanation",
    "confidence": 0.0-1.0
}}

Examples:
- "What tools are available?" -> {{"needs_context": false, "reason": "Standalone question", "confidence": 0.9}}
- "Show me that again" -> {{"needs_context": true, "reason": "References previous output", "confidence": 0.95}}
- "Create a profile called 'engineer'" -> {{"needs_context": false, "reason": "Complete standalone command", "confidence": 0.95}}
- "Why did that fail?" -> {{"needs_context": true, "reason": "References previous action", "confidence": 0.9}}

Respond ONLY with the JSON object, no other text."""

        try:
            response = requests.post(
                f"{self.llama_url}/completion",
                json={
                    "prompt": prompt,
                    "temperature": 0.1,  # Very low for consistent analysis
                    "max_tokens": 200,
                    "stop": ["\n\n", "---"],
                },
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get("content", "").strip()

                # Extract JSON from response
                try:
                    # Find JSON object in response
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        analysis = json.loads(content[start:end])

                        return {
                            "needs_context": analysis.get("needs_context", False),
                            "reason": analysis.get("reason", "LLM analysis"),
                            "relevant_messages": [],  # Could be enhanced to identify specific messages
                            "confidence": analysis.get("confidence", 0.7),
                        }
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM analysis response: {content}")

        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")

        # Fallback to heuristic result
        return self._heuristic_check(message)

    def filter_context(
        self,
        conversation_history: List[Dict[str, Any]],
        relevant_indices: Optional[List[int]] = None,
        max_messages: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Filter conversation history to relevant messages

        Args:
            conversation_history: Full conversation history
            relevant_indices: Specific message indices to include (optional)
            max_messages: Maximum messages to include

        Returns:
            Filtered conversation history
        """
        if not conversation_history:
            return []

        # If specific indices provided, use those
        if relevant_indices:
            return [
                conversation_history[i]
                for i in relevant_indices
                if 0 <= i < len(conversation_history)
            ]

        # Otherwise return recent messages up to max
        return conversation_history[-max_messages:]

    def get_context_summary(
        self,
        analysis: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a summary of context decision for logging

        Args:
            analysis: Analysis result
            conversation_history: Conversation history

        Returns:
            Human-readable summary
        """
        if analysis["needs_context"]:
            context_size = len(self.filter_context(conversation_history))
            return (
                f"Using {context_size} previous messages "
                f"({analysis['reason']}, confidence: {analysis['confidence']:.0%})"
            )
        else:
            return (
                f"Standalone message "
                f"({analysis['reason']}, confidence: {analysis['confidence']:.0%})"
            )

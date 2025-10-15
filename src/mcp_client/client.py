"""
MCP Client - Core Implementation

Main client class that orchestrates LLM ↔ MCP server communication.
"""

import json
import requests
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from .llm_interface import LlamaServerInterface
from .tool_schema import ToolSchemaGenerator
from .context_relevance import ContextRelevanceAnalyzer

logger = logging.getLogger(__name__)


class MCPClient:
    """Main MCP client for local LLM integration"""

    def __init__(
        self,
        llama_url: str = "http://localhost:8080",
        mcp_url: str = "http://localhost:3000",
        mcp_token: Optional[str] = None,
        max_iterations: int = 10,
    ):
        """
        Initialize MCP client

        Args:
            llama_url: llama-server URL
            mcp_url: MCP server URL
            mcp_token: MCP authentication token
            max_iterations: Maximum tool call iterations per request
        """
        self.llama_url = llama_url
        self.mcp_url = mcp_url.rstrip("/")
        self.mcp_token = mcp_token
        self.max_iterations = max_iterations

        # Initialize components
        self.llm = LlamaServerInterface(base_url=llama_url)
        self.schema_gen = ToolSchemaGenerator(mcp_url=mcp_url, auth_token=mcp_token)
        self.context_analyzer = ContextRelevanceAnalyzer(llama_url=llama_url)

        # Load system prompt
        self.system_prompt_template = self._load_system_prompt()

        # Conversation history
        self.messages: List[Dict[str, Any]] = []

        # Context filtering settings
        self.enable_context_filtering = True  # Can be toggled
        self.max_context_messages = 10  # Maximum messages to consider

    def _load_system_prompt(self) -> str:
        """Load system prompt template"""
        prompt_file = Path(__file__).parent / "prompts" / "system_prompt.txt"

        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                return f.read()
        else:
            # Fallback basic prompt
            return "You are an AI assistant. Use tools when needed. Respond in JSON format."

    def _build_system_prompt(self) -> str:
        """
        Build complete system prompt with tool schemas

        Returns:
            Complete system prompt
        """
        # Get tool schemas
        tool_schemas_formatted = self.schema_gen.format_for_llm()

        # Inject into template
        return self.system_prompt_template.replace("{tool_schemas}", tool_schemas_formatted)

    def chat(self, user_message: str, verbose: bool = False, progress_callback=None) -> str:
        """
        Main entry point for user messages

        Args:
            user_message: User's message
            verbose: Enable verbose logging
            progress_callback: Optional callback function to report progress
                              Called with dict: {"stage": str, "tool": str, "status": str}

        Returns:
            Final response to user
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Analyze context needs
        context_analysis = None
        filtered_messages = self.messages

        if self.enable_context_filtering and len(self.messages) > 1:
            context_analysis = self.context_analyzer.analyze_message(
                message=user_message,
                conversation_history=self.messages[:-1],  # Exclude current message
                max_history=self.max_context_messages,
            )

            if verbose:
                summary = self.context_analyzer.get_context_summary(
                    context_analysis,
                    self.messages[:-1]
                )
                logger.info(f"Context Analysis: {summary}")

            if not context_analysis["needs_context"]:
                # Use only the current message
                filtered_messages = [self.messages[-1]]
                if verbose:
                    logger.info("Processing as standalone message (no context)")
            else:
                # Use filtered context
                context_messages = self.context_analyzer.filter_context(
                    self.messages[:-1],
                    relevant_indices=context_analysis.get("relevant_messages"),
                    max_messages=5,  # Keep last 5 relevant messages
                )
                filtered_messages = context_messages + [self.messages[-1]]
                if verbose:
                    logger.info(f"Using {len(context_messages)} context messages")

        # Build system prompt
        system_prompt = self._build_system_prompt()

        # Loop detection: track recent tool calls
        recent_tool_calls = []  # List of (tool_name, parameters) tuples

        # Agentic loop
        for iteration in range(self.max_iterations):
            if verbose:
                logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")

            # Notify callback that we're thinking
            if progress_callback:
                progress_callback({
                    "stage": "thinking",
                    "status": "processing",
                    "iteration": iteration + 1
                })

            # Format conversation for LLM (using filtered messages)
            conversation = self.llm.format_chat_messages(filtered_messages)

            # Get LLM response
            try:
                response = self.llm.complete(
                    prompt=conversation,
                    system_prompt=system_prompt,
                    json_mode=True,
                )

                if not response.get("parsed"):
                    # Failed to parse JSON
                    logger.error(f"JSON parse failure on iteration {iteration + 1}")

                    # On first failure, try once more with a corrective message
                    if iteration == 0:
                        correction_msg = (
                            "IMPORTANT: Your last response was not valid JSON. "
                            "You MUST respond with a single, valid JSON object containing EITHER:\n"
                            '1. {"thought": "...", "tool": "...", "parameters": {...}} OR\n'
                            '2. {"thought": "...", "response": "..."}\n'
                            "Output only the JSON object, nothing else. Stop after the closing brace."
                        )
                        filtered_messages.append({
                            "role": "system",
                            "content": correction_msg
                        })
                        continue  # Try again

                    # Second failure - give up
                    error_msg = "I apologize, but I had trouble formatting my response properly. Could you please rephrase your request?"
                    self.messages.append({"role": "assistant", "content": error_msg})
                    return error_msg

                parsed = response["parsed"]

                # Check if this is a final response
                if "response" in parsed:
                    # Final answer
                    final_response = parsed["response"]
                    thought = parsed.get("thought", "")

                    if verbose and thought:
                        logger.info(f"Thought: {thought}")

                    self.messages.append({"role": "assistant", "content": final_response})
                    return final_response

                # Check if this is a tool call
                if "tool" in parsed and "parameters" in parsed:
                    tool_name = parsed["tool"]
                    parameters = parsed["parameters"]
                    thought = parsed.get("thought", "")

                    if verbose:
                        logger.info(f"Thought: {thought}")
                        logger.info(f"Tool: {tool_name}")
                        logger.info(f"Parameters: {parameters}")

                    # Notify progress callback IMMEDIATELY after parsing tool name
                    # This ensures the UI updates before the tool execution starts
                    if progress_callback:
                        progress_callback({
                            "stage": "tool_executing",
                            "tool": tool_name,
                            "status": "running"
                        })

                    # Loop detection: check if this exact tool call was just made
                    tool_call_signature = (tool_name, json.dumps(parameters, sort_keys=True))

                    # Check last 3 tool calls for identical calls
                    if tool_call_signature in recent_tool_calls[-3:]:
                        logger.warning(f"Loop detected: {tool_name} called repeatedly with same parameters")
                        error_msg = (
                            f"I notice I'm repeating the same action ({tool_name}). "
                            "This suggests I may be stuck in a loop. Could you please rephrase "
                            "your request or provide more specific information?"
                        )
                        self.messages.append({"role": "assistant", "content": error_msg})
                        return error_msg

                    # Add to recent calls (keep last 5)
                    recent_tool_calls.append(tool_call_signature)
                    if len(recent_tool_calls) > 5:
                        recent_tool_calls.pop(0)

                    # Execute tool
                    tool_result = self._execute_tool(tool_name, parameters)

                    # Notify progress callback after tool execution
                    if progress_callback:
                        progress_callback({
                            "stage": "tool_completed",
                            "tool": tool_name,
                            "status": "completed"
                        })

                    # Add tool call and result to history
                    tool_message = {
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(tool_result, indent=2),
                    }
                    self.messages.append(tool_message)

                    # Also add to filtered messages for this iteration
                    if len(filtered_messages) > 0:
                        filtered_messages.append(tool_message)

                    # Continue loop to let LLM process result
                    continue

                else:
                    # Invalid response format
                    error_msg = "I received an unexpected response format. Let me try again."
                    self.messages.append({"role": "assistant", "content": error_msg})
                    return error_msg

            except Exception as e:
                logger.error(f"Error in chat loop: {e}")
                error_msg = f"I encountered an error: {str(e)}. Please try again."
                self.messages.append({"role": "assistant", "content": error_msg})
                return error_msg

        # Max iterations reached
        timeout_msg = "I've reached the maximum number of steps for this request. Please try breaking it into smaller tasks."
        self.messages.append({"role": "assistant", "content": timeout_msg})
        return timeout_msg

    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool via MCP server

        Args:
            tool_name: Tool name (category.action)
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        try:
            headers = {"Content-Type": "application/json"}
            if self.mcp_token:
                headers["Authorization"] = f"Bearer {self.mcp_token}"

            payload = {
                "tool": tool_name,
                "parameters": parameters,
            }

            response = requests.post(
                f"{self.mcp_url}/tools/execute",
                json=payload,
                headers=headers,
                timeout=300,  # 5 minutes for long-running operations
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "ToolExecutionError",
            }

    def get_resource(self, uri: str) -> Dict[str, Any]:
        """
        Get resource from MCP server

        Args:
            uri: Resource URI (e.g., "profile://default/config")

        Returns:
            Resource data
        """
        try:
            headers = {"Content-Type": "application/json"}
            if self.mcp_token:
                headers["Authorization"] = f"Bearer {self.mcp_token}"

            payload = {"uri": uri}

            response = requests.post(
                f"{self.mcp_url}/resources/get",
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Resource retrieval failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def clear_conversation(self):
        """Clear conversation history"""
        self.messages = []

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get conversation history

        Returns:
            List of messages
        """
        return self.messages.copy()

    def health_check(self) -> Dict[str, Any]:
        """
        Check health of all services

        Returns:
            Dict with health status of each service including detailed status
        """
        result = {}

        # Check llama-server
        try:
            llama_health = self.llm.health_check()
            result["llama_server"] = llama_health["status"]
            result["llama_message"] = llama_health["message"]
        except Exception as e:
            result["llama_server"] = "offline"
            result["llama_message"] = f"Health check failed: {str(e)}"

        # Check MCP server
        try:
            response = requests.get(f"{self.mcp_url}/health", timeout=5)
            if response.status_code == 200:
                result["mcp_server"] = "online"
                result["mcp_message"] = "Server is ready"
            else:
                result["mcp_server"] = "offline"
                result["mcp_message"] = f"Status code: {response.status_code}"
        except requests.exceptions.ConnectionError:
            result["mcp_server"] = "offline"
            result["mcp_message"] = "Connection refused"
        except Exception as e:
            result["mcp_server"] = "offline"
            result["mcp_message"] = f"Error: {str(e)}"

        # Overall status (only online if both services are online)
        result["overall"] = (
            result["llama_server"] == "online" and
            result["mcp_server"] == "online"
        )

        return result

    def list_tools(self) -> List[str]:
        """
        List all available tools

        Returns:
            List of tool names
        """
        return self.schema_gen.get_tool_names()

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific tool

        Args:
            tool_name: Tool name

        Returns:
            Tool schema or None if not found
        """
        schemas = self.schema_gen.get_tool_schemas()
        return schemas.get(tool_name)

    def set_context_filtering(self, enabled: bool):
        """
        Enable or disable context filtering

        Args:
            enabled: Whether to enable context filtering
        """
        self.enable_context_filtering = enabled
        logger.info(f"Context filtering {'enabled' if enabled else 'disabled'}")

    def get_context_stats(self) -> Dict[str, Any]:
        """
        Get statistics about context usage

        Returns:
            Dict with context statistics
        """
        return {
            "total_messages": len(self.messages),
            "context_filtering_enabled": self.enable_context_filtering,
            "max_context_messages": self.max_context_messages,
        }

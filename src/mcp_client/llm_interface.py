"""
LLM Interface for llama-server

Handles communication with llama-server for LLM inference.
"""

import json
import requests
from typing import Dict, Any, Optional, Iterator
import logging

logger = logging.getLogger(__name__)


class LlamaServerInterface:
    """Interface for communicating with llama-server"""

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: int = 300,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ):
        """
        Initialize LlamaServer interface

        Args:
            base_url: llama-server URL
            timeout: Request timeout in seconds
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[list] = None,
        json_mode: bool = True,
    ) -> Dict[str, Any]:
        """
        Get completion from llama-server

        Args:
            prompt: User prompt
            system_prompt: System prompt
            max_tokens: Override default max_tokens
            temperature: Override default temperature
            stop: Stop sequences
            json_mode: Enable JSON mode for structured output

        Returns:
            Response dict with 'content' and metadata
        """
        # Build full prompt with system prompt if provided
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        else:
            full_prompt = prompt

        # Prepare request
        payload = {
            "prompt": full_prompt,
            "n_predict": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stop": stop or [],
            "stream": False,
        }

        # Disable grammar enforcement - it can cause infinite loops with nested JSON
        # Instead, we rely on strong system prompt guidance and post-processing validation
        # if json_mode:
        #     payload["grammar"] = self._get_json_grammar()

        try:
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            data = response.json()
            content = data.get("content", "").strip()

            # Try to parse as JSON if in json_mode
            if json_mode:
                try:
                    # Clean up common JSON issues before parsing
                    cleaned_content = content.strip()

                    # Remove markdown code blocks if present
                    if cleaned_content.startswith("```"):
                        lines = cleaned_content.split("\n")
                        cleaned_content = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned_content

                    # Find the first valid JSON object (helps with infinite loop outputs)
                    # Look for first { and find its matching }
                    start_idx = cleaned_content.find("{")
                    if start_idx != -1:
                        brace_count = 0
                        end_idx = -1
                        for i in range(start_idx, len(cleaned_content)):
                            if cleaned_content[i] == "{":
                                brace_count += 1
                            elif cleaned_content[i] == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i + 1
                                    break

                        if end_idx != -1:
                            cleaned_content = cleaned_content[start_idx:end_idx]

                    parsed = json.loads(cleaned_content)

                    # Validate structure
                    if not isinstance(parsed, dict):
                        raise ValueError("JSON must be an object, not array or primitive")

                    # Check for required fields
                    has_tool = "tool" in parsed and "parameters" in parsed
                    has_response = "response" in parsed

                    if not (has_tool or has_response):
                        logger.warning(f"JSON missing required fields: {parsed.keys()}")

                    return {
                        "content": cleaned_content,
                        "parsed": parsed,
                        "tokens_predicted": data.get("tokens_predicted", 0),
                        "tokens_evaluated": data.get("tokens_evaluated", 0),
                    }
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse JSON response: {content[:200]}")
                    return {
                        "content": content,
                        "parsed": None,
                        "tokens_predicted": data.get("tokens_predicted", 0),
                        "tokens_evaluated": data.get("tokens_evaluated", 0),
                        "error": f"Failed to parse JSON: {str(e)}",
                    }

            return {
                "content": content,
                "tokens_predicted": data.get("tokens_predicted", 0),
                "tokens_evaluated": data.get("tokens_evaluated", 0),
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Request to llama-server failed: {e}")
            raise ConnectionError(f"Failed to connect to llama-server: {e}")

    def stream_complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[list] = None,
    ) -> Iterator[str]:
        """
        Stream completion from llama-server

        Args:
            prompt: User prompt
            system_prompt: System prompt
            max_tokens: Override default max_tokens
            temperature: Override default temperature
            stop: Stop sequences

        Yields:
            Token strings as they are generated
        """
        # Build full prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:"
        else:
            full_prompt = prompt

        # Prepare request
        payload = {
            "prompt": full_prompt,
            "n_predict": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stop": stop or [],
            "stream": True,
        }

        try:
            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            response.raise_for_status()

            # Stream tokens
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode("utf-8").replace("data: ", ""))
                        if "content" in data:
                            yield data["content"]

                        # Check for stop
                        if data.get("stop", False):
                            break

                    except json.JSONDecodeError:
                        continue

        except requests.exceptions.RequestException as e:
            logger.error(f"Stream request failed: {e}")
            raise ConnectionError(f"Failed to stream from llama-server: {e}")

    def health_check(self) -> Dict[str, Any]:
        """
        Check if llama-server is available

        Returns:
            Dict with 'status' (online/loading/offline) and 'message'
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)

            if response.status_code == 200:
                # Server is ready
                return {
                    "status": "online",
                    "message": "Server is ready"
                }
            elif response.status_code == 503:
                # Server is loading model
                try:
                    data = response.json()
                    error_msg = data.get("error", {}).get("message", "Loading")
                    return {
                        "status": "loading",
                        "message": error_msg
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "loading",
                        "message": "Server is starting"
                    }
            else:
                # Unexpected status code
                return {
                    "status": "offline",
                    "message": f"Unexpected status code: {response.status_code}"
                }

        except requests.exceptions.ConnectionError:
            return {
                "status": "offline",
                "message": "Connection refused - server not running"
            }
        except requests.exceptions.Timeout:
            return {
                "status": "offline",
                "message": "Connection timeout"
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "offline",
                "message": f"Request failed: {str(e)}"
            }

    def _get_json_grammar(self) -> str:
        """
        Get GBNF grammar for JSON output

        Returns:
            Grammar string for llama.cpp JSON mode
        """
        # Simple JSON grammar for tool calls
        return """
root ::= object
object ::= "{" ws members ws "}"
members ::= pair (ws "," ws pair)*
pair ::= string ws ":" ws value
string ::= "\\"" [^"]* "\\""
value ::= object | array | string | number | boolean | null
array ::= "[" ws elements? ws "]"
elements ::= value (ws "," ws value)*
number ::= "-"? [0-9]+ ("." [0-9]+)?
boolean ::= "true" | "false"
null ::= "null"
ws ::= [ \\t\\n]*
"""

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text

        Args:
            text: Text to count

        Returns:
            Estimated token count (rough approximation)
        """
        # Rough approximation: 1 token ≈ 4 characters for English
        # Qwen models use similar tokenization to GPT
        return len(text) // 4

    def format_chat_messages(self, messages: list) -> str:
        """
        Format chat messages for Qwen3 chat template

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Formatted prompt string
        """
        formatted = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
            elif role == "tool":
                tool_name = msg.get("name", "tool")
                formatted.append(f"Tool ({tool_name}): {content}")

        return "\n\n".join(formatted)

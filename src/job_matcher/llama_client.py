"""
LlamaClient - API client for communicating with llama-server

Provides a clean interface for sending prompts to llama-server and
receiving AI-generated responses.
"""

import os
import json
import ast
import requests
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()


class LlamaClient:
    """Client for interacting with llama-server API"""

    @staticmethod
    def _try_urls(urls: List[str]) -> str:
        """
        Try a list of URLs and return the first one that responds

        Args:
            urls: List of llama-server URLs to try

        Returns:
            The first working URL, or the first URL as fallback
        """
        if not urls:
            return "http://localhost:8080"

        for url in urls:
            try:
                # Quick health check with short timeout
                response = requests.get(f"{url.rstrip('/')}/health", timeout=2)
                if response.status_code == 200:
                    return url
            except Exception:
                # Connection failed, try next URL
                continue

        # If all fail, return first URL as fallback
        return urls[0]

    def __init__(
        self,
        server_url: Optional[str] = None,
        context_size: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        request_timeout: Optional[int] = None,
    ):
        """
        Initialize LlamaClient

        Args:
            server_url: URL of the llama-server (default: from .env)
                       Can be a single URL or a list of URLs to try in order
            context_size: Maximum context window size (default: from .env)
            temperature: Sampling temperature (default: from .env)
            max_tokens: Maximum tokens to generate (default: from .env)
            request_timeout: Request timeout in seconds (default: from .env, 300s)
        """
        # Determine server URL
        if server_url:
            # Explicit parameter takes priority
            self.server_url = server_url
        else:
            # Read from .env
            env_url = os.getenv("LLAMA_SERVER_URL", "http://localhost:8080")

            # Try to parse as list (supports multiple formats)
            if env_url.strip().startswith('[') and env_url.strip().endswith(']'):
                # Legacy format: [url1, url2] - try Python list syntax first (with quotes)
                try:
                    urls = ast.literal_eval(env_url)
                    if isinstance(urls, list) and urls:
                        # Try each URL and use first working one
                        self.server_url = self._try_urls(urls)
                    else:
                        self.server_url = env_url
                except (ValueError, SyntaxError):
                    # Fall back to manual parsing for unquoted URLs
                    # Remove brackets and split by comma
                    url_string = env_url.strip()[1:-1]  # Remove [ and ]
                    urls = [url.strip() for url in url_string.split(',') if url.strip()]
                    if urls:
                        # Try each URL and use first working one
                        self.server_url = self._try_urls(urls)
                    else:
                        self.server_url = "http://localhost:8080"
            elif ',' in env_url:
                # New format: url1,url2,url3 - comma-separated URLs
                urls = [url.strip() for url in env_url.split(',') if url.strip()]
                if urls:
                    # Try each URL and use first working one
                    self.server_url = self._try_urls(urls)
                else:
                    self.server_url = "http://localhost:8080"
            else:
                # Single URL
                self.server_url = env_url

        self.context_size = context_size or int(
            os.getenv("LLAMA_CONTEXT_SIZE", "8192")
        )
        self.temperature = temperature or float(os.getenv("LLAMA_TEMPERATURE", "0.3"))
        self.max_tokens = max_tokens or int(os.getenv("LLAMA_MAX_TOKENS", "2048"))
        self.request_timeout = request_timeout or int(os.getenv("LLAMA_REQUEST_TIMEOUT", "300"))

        # Ensure server_url doesn't have trailing slash
        self.server_url = self.server_url.rstrip("/")

        # Debug: Print selected URL (only once during initialization)
        if not server_url and env_url and (',' in env_url or env_url.strip().startswith('[')):
            print(f"[INFO] Selected llama-server URL: {self.server_url}")

    def test_connection(self) -> bool:
        """
        Test connection to llama-server

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            if response.status_code == 200:
                return True
            else:
                print(f"X Connection test failed: Server returned status {response.status_code}")
                print(f"  URL: {self.server_url}/health")
                return False
        except requests.exceptions.ConnectionError:
            print(f"X Connection test failed: Unable to connect to llama-server")
            print(f"  URL: {self.server_url}/health")
            print(f"  Hint: Is llama-server running at this address?")
            return False
        except requests.exceptions.Timeout:
            print(f"X Connection test failed: Request timed out after 5 seconds")
            print(f"  URL: {self.server_url}/health")
            return False
        except Exception as e:
            print(f"X Connection test failed: {type(e).__name__}: {e}")
            print(f"  URL: {self.server_url}/health")
            return False

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[list] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate text completion from llama-server

        Args:
            prompt: The prompt to send to the model
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            stop: List of stop sequences
            json_schema: Optional JSON schema to enforce output format

        Returns:
            Generated text or None if request fails
        """
        try:
            payload = {
                "prompt": prompt,
                "temperature": temperature or self.temperature,
                "n_predict": max_tokens or self.max_tokens,
                "stop": stop or [],
                "stream": False,
            }

            # Add JSON schema if provided (llama.cpp supports this)
            if json_schema:
                payload["json_schema"] = json_schema

            response = requests.post(
                f"{self.server_url}/completion",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.request_timeout,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("content", "").strip()
            else:
                print(f"X Generation failed: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            print(f"X Request timed out after {self.request_timeout} seconds")
            return None
        except Exception as e:
            print(f"X Generation error: {e}")
            return None

    def generate_json(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate JSON response from llama-server

        Args:
            prompt: The prompt to send to the model
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            json_schema: Optional JSON schema to enforce output format

        Returns:
            Parsed JSON dict or None if request fails
        """
        # Add JSON instruction to prompt
        json_prompt = f"{prompt}\n\nYou MUST respond with ONLY valid JSON. Do not include explanations, thinking, or any text outside the JSON object."

        result = self.generate(
            prompt=json_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_schema=json_schema
        )

        if not result:
            return None

        # Try multiple strategies to extract JSON from response
        import re

        # Strategy 1: Direct parse
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from ```json code block
        if "```json" in result:
            try:
                extracted = result.split("```json")[1].split("```")[0].strip()
                return json.loads(extracted)
            except (IndexError, json.JSONDecodeError):
                pass

        # Strategy 3: Extract from generic ``` code block
        if "```" in result:
            try:
                extracted = result.split("```")[1].split("```")[0].strip()
                # Remove language identifier if present (e.g., "json\n")
                if extracted.startswith("json"):
                    extracted = extracted[4:].strip()
                return json.loads(extracted)
            except (IndexError, json.JSONDecodeError):
                pass

        # Strategy 4: Handle thinking models - find first valid JSON after thinking text
        # Look for the first opening brace and try to extract a complete JSON object from there
        first_brace = result.find("{")
        if first_brace != -1:
            try:
                # Count braces to find matching closing brace
                brace_count = 0
                in_string = False
                escape_next = False

                for i, char in enumerate(result[first_brace:], first_brace):
                    if escape_next:
                        escape_next = False
                        continue

                    if char == '\\':
                        escape_next = True
                        continue

                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue

                    if not in_string:
                        if char == "{":
                            brace_count += 1
                        elif char == "}":
                            brace_count -= 1
                            if brace_count == 0:
                                json_str = result[first_brace:i+1]
                                parsed = json.loads(json_str)
                                if isinstance(parsed, dict) and len(parsed) > 0:
                                    return parsed
                                break
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 5: Find JSON object using regex (nested braces supported)
        # Match complete JSON objects with proper nesting
        json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
        matches = re.findall(json_pattern, result, re.DOTALL)

        for match in matches:
            try:
                parsed = json.loads(match)
                # Verify it looks like our expected format (has reasonable keys)
                if isinstance(parsed, dict) and len(parsed) > 0:
                    return parsed
            except json.JSONDecodeError:
                continue

        # Strategy 6: Try to find JSON between common delimiters
        for start_marker in ["JSON:", "json:", "Response:", "Output:"]:
            if start_marker in result:
                try:
                    json_portion = result.split(start_marker, 1)[1].strip()
                    # Try to parse the first { ... } found
                    first_brace = json_portion.find("{")
                    if first_brace != -1:
                        # Find matching closing brace
                        brace_count = 0
                        for i, char in enumerate(json_portion[first_brace:], first_brace):
                            if char == "{":
                                brace_count += 1
                            elif char == "}":
                                brace_count -= 1
                                if brace_count == 0:
                                    json_str = json_portion[first_brace:i+1]
                                    return json.loads(json_str)
                except (json.JSONDecodeError, ValueError):
                    continue

        # All strategies failed
        # Note: Error logging handled by caller (failure tracker)
        # Removed print statements to avoid thread output conflicts in multi-threaded execution
        return None

    async def generate_json_batch_async(
        self,
        prompts: List[str],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Generate JSON responses for multiple prompts simultaneously using async HTTP

        This method submits ALL prompts to llama-server simultaneously, allowing
        the server to process them in parallel and maintain constant GPU load.

        Args:
            prompts: List of prompts to send to the model
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            json_schema: Optional JSON schema to enforce output format

        Returns:
            List of parsed JSON dicts (or None for failed requests), in same order as prompts
        """
        import aiohttp
        import asyncio

        async def single_request(session: aiohttp.ClientSession, prompt: str, index: int) -> tuple[int, Optional[Dict[str, Any]]]:
            """
            Execute a single async request

            Args:
                session: aiohttp session
                prompt: The prompt to send
                index: Original position in prompts list

            Returns:
                Tuple of (index, result_dict or None)
            """
            # Add JSON instruction to prompt
            json_prompt = f"{prompt}\n\nYou MUST respond with ONLY valid JSON. Do not include explanations, thinking, or any text outside the JSON object."

            payload = {
                "prompt": json_prompt,
                "temperature": temperature or self.temperature,
                "n_predict": max_tokens or self.max_tokens,
                "stop": [],
                "stream": False,
            }

            # Add JSON schema if provided
            if json_schema:
                payload["json_schema"] = json_schema

            try:
                async with session.post(
                    f"{self.server_url}/completion",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=self.request_timeout),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result.get("content", "").strip()

                        # Parse JSON from content using same strategies as generate_json()
                        # Strategy 1: Direct parse
                        try:
                            return (index, json.loads(content))
                        except json.JSONDecodeError:
                            pass

                        # Strategy 2: Extract from ```json code block
                        if "```json" in content:
                            try:
                                extracted = content.split("```json")[1].split("```")[0].strip()
                                return (index, json.loads(extracted))
                            except (IndexError, json.JSONDecodeError):
                                pass

                        # Strategy 3: Extract from generic ``` code block
                        if "```" in content:
                            try:
                                extracted = content.split("```")[1].split("```")[0].strip()
                                if extracted.startswith("json"):
                                    extracted = extracted[4:].strip()
                                return (index, json.loads(extracted))
                            except (IndexError, json.JSONDecodeError):
                                pass

                        # Strategy 4: Find first valid JSON object
                        first_brace = content.find("{")
                        if first_brace != -1:
                            try:
                                brace_count = 0
                                in_string = False
                                escape_next = False

                                for i, char in enumerate(content[first_brace:], first_brace):
                                    if escape_next:
                                        escape_next = False
                                        continue

                                    if char == '\\':
                                        escape_next = True
                                        continue

                                    if char == '"' and not escape_next:
                                        in_string = not in_string
                                        continue

                                    if not in_string:
                                        if char == "{":
                                            brace_count += 1
                                        elif char == "}":
                                            brace_count -= 1
                                            if brace_count == 0:
                                                json_str = content[first_brace:i+1]
                                                parsed = json.loads(json_str)
                                                if isinstance(parsed, dict) and len(parsed) > 0:
                                                    return (index, parsed)
                                                break
                            except (json.JSONDecodeError, ValueError):
                                pass

                        # All parsing strategies failed
                        return (index, None)
                    else:
                        # HTTP error
                        return (index, None)

            except asyncio.TimeoutError:
                return (index, None)
            except Exception as e:
                return (index, None)

        # Create aiohttp session with unlimited concurrent connections
        # This ensures ALL requests hit llama-server simultaneously
        connector = aiohttp.TCPConnector(
            limit=0,  # 0 = unlimited total connections
            limit_per_host=0,  # 0 = unlimited connections per host (critical for batch mode)
            force_close=False,  # Reuse connections for efficiency
            enable_cleanup_closed=True
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [
                single_request(session, prompt, idx)
                for idx, prompt in enumerate(prompts)
            ]
            # Gather all results simultaneously - all HTTP requests fire at once
            indexed_results = await asyncio.gather(*tasks)

        # Sort by index to maintain original order
        indexed_results.sort(key=lambda x: x[0])
        results = [result for _, result in indexed_results]

        return results

    def chat(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """
        Send chat messages to llama-server

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Generated response or None if request fails
        """
        # Convert chat messages to a single prompt
        # Format: <|im_start|>role\ncontent<|im_end|>
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")

        # Add assistant start token
        prompt_parts.append("<|im_start|>assistant\n")

        prompt = "\n".join(prompt_parts)

        return self.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=["<|im_end|>"],
        )

    def get_model_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the loaded model

        Returns:
            Model info dict or None if request fails
        """
        try:
            response = requests.get(f"{self.server_url}/props", timeout=5)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"X Failed to get model info: {e}")
            return None


if __name__ == "__main__":
    # Test the client
    print("Testing LlamaClient connection...")
    client = LlamaClient()

    print(f"Server URL: {client.server_url}")
    print(f"Context Size: {client.context_size}")
    print(f"Temperature: {client.temperature}")
    print(f"Max Tokens: {client.max_tokens}")
    print()

    if client.test_connection():
        print("Connection successful!")

        # Get model info
        info = client.get_model_info()
        if info:
            print("\nModel Info:")
            print(json.dumps(info, indent=2))

        # Test generation
        print("\nTesting generation...")
        response = client.generate(
            "Say 'Hello from llama-server!' in a friendly way.", max_tokens=50
        )
        if response:
            print(f"Response: {response}")
    else:
        print("X Connection failed. Is llama-server running?")

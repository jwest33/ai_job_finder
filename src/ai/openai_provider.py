"""
OpenAI-Compatible AI Provider

Implements the AIProvider interface for OpenAI-compatible APIs.
Works with: llama-server, Ollama, vLLM, LM Studio, OpenAI, Azure OpenAI, etc.
"""

import asyncio
import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests

from .provider import AIProvider, AICapabilities, ConnectionTestResult
from .settings import AISettings

logger = logging.getLogger(__name__)


# Try to import aiohttp for async batch operations
try:
    import aiohttp
    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False


class OpenAICompatibleProvider(AIProvider):
    """
    AI Provider for OpenAI-compatible APIs.

    Supports the standard OpenAI API format (/v1/chat/completions, /v1/models, etc.)
    which is implemented by many providers including:
    - OpenAI
    - Azure OpenAI
    - llama.cpp server (with -oai flag)
    - Ollama
    - vLLM
    - LM Studio
    - text-generation-inference
    """

    def __init__(self, settings: AISettings):
        """
        Initialize the provider.

        Args:
            settings: AISettings with configuration
        """
        self._settings = settings
        self._base_url = settings.base_url.rstrip("/")
        self._api_key = settings.api_key or ""
        self._model = settings.model
        self._vision_model = settings.get_effective_vision_model()
        self._temperature = settings.temperature
        self._max_tokens = settings.max_tokens
        self._timeout = settings.timeout
        self._max_concurrent = settings.max_concurrent

        # Cached capabilities (updated on test_connection)
        self._capabilities = AICapabilities(
            text=True,
            vision=settings.vision_enabled if settings.vision_enabled is not None else False
        )

    @property
    def server_url(self) -> str:
        """Get the base API URL."""
        return self._base_url

    @property
    def has_vision(self) -> bool:
        """Check if vision is available."""
        return self._capabilities.vision

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from response content using multiple strategies.

        Args:
            content: Raw response content

        Returns:
            Parsed JSON dict or None
        """
        if not content:
            return None

        # Strategy 1: Direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from ```json code block
        if "```json" in content:
            try:
                extracted = content.split("```json")[1].split("```")[0].strip()
                return json.loads(extracted)
            except (IndexError, json.JSONDecodeError):
                pass

        # Strategy 3: Extract from generic ``` code block
        if "```" in content:
            try:
                extracted = content.split("```")[1].split("```")[0].strip()
                if extracted.startswith("json"):
                    extracted = extracted[4:].strip()
                return json.loads(extracted)
            except (IndexError, json.JSONDecodeError):
                pass

        # Strategy 4: Find first valid JSON object with brace matching
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
                                    return parsed
                                break
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 5: Find JSON using regex
        json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)

        for match in matches:
            try:
                parsed = json.loads(match)
                if isinstance(parsed, dict) and len(parsed) > 0:
                    return parsed
            except json.JSONDecodeError:
                continue

        return None

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate text completion."""
        try:
            messages = [{"role": "user", "content": prompt}]

            payload = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self._temperature,
                "max_tokens": max_tokens or self._max_tokens,
                "stream": False,
            }

            if stop:
                payload["stop"] = stop

            # Add response format for JSON if schema provided
            if json_schema:
                payload["response_format"] = {"type": "json_object"}

            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=self._timeout,
            )

            if response.status_code == 200:
                result = response.json()
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    return message.get("content", "").strip()
            else:
                logger.error(f"Generation failed: {response.status_code} - {response.text[:500]}")

            return None

        except requests.exceptions.Timeout:
            logger.error(f"Request timed out after {self._timeout} seconds")
            return None
        except Exception as e:
            logger.exception(f"Generation error: {e}")
            return None

    def generate_json(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate JSON response."""
        # Add JSON instruction to prompt
        json_prompt = f"{prompt}\n\nYou MUST respond with ONLY valid JSON. Do not include explanations, thinking, or any text outside the JSON object."

        result = self.generate(
            prompt=json_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_schema=json_schema,
        )

        if not result:
            return None

        return self._extract_json(result)

    async def generate_batch_async(
        self,
        prompts: List[str],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        max_concurrent: Optional[int] = None,
    ) -> List[Optional[Dict[str, Any]]]:
        """Generate JSON responses for multiple prompts concurrently."""
        if not ASYNC_AVAILABLE:
            raise RuntimeError(
                "Async batch mode not available: aiohttp not installed. "
                "Install with: pip install aiohttp>=3.9.0"
            )

        max_concurrent = max_concurrent or self._max_concurrent
        logger.info(f"Processing {len(prompts)} prompts in batches of {max_concurrent}")

        async def single_request(
            session: aiohttp.ClientSession,
            prompt: str,
            index: int
        ) -> tuple[int, Optional[Dict[str, Any]]]:
            """Execute a single async request."""
            json_prompt = f"{prompt}\n\nYou MUST respond with ONLY valid JSON. Do not include explanations, thinking, or any text outside the JSON object."

            messages = [{"role": "user", "content": json_prompt}]

            payload = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self._temperature,
                "max_tokens": max_tokens or self._max_tokens,
                "stream": False,
            }

            if json_schema:
                payload["response_format"] = {"type": "json_object"}

            try:
                async with session.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        choices = result.get("choices", [])
                        if choices:
                            content = choices[0].get("message", {}).get("content", "").strip()
                            parsed = self._extract_json(content)
                            return (index, parsed)
                    else:
                        error_text = await response.text()
                        if index < 3:
                            logger.error(f"HTTP error for request {index}: {response.status} - {error_text[:500]}")
                    return (index, None)

            except asyncio.TimeoutError:
                if index < 3:
                    logger.error(f"Request {index} timed out after {self._timeout}s")
                return (index, None)
            except Exception as e:
                if index < 3:
                    logger.error(f"Request {index} failed: {type(e).__name__}: {str(e)}")
                return (index, None)

        # Create session with connection limit
        connector = aiohttp.TCPConnector(
            limit=max_concurrent,
            limit_per_host=max_concurrent,
            force_close=False,
            enable_cleanup_closed=True
        )

        all_results = []

        async with aiohttp.ClientSession(connector=connector) as session:
            for batch_start in range(0, len(prompts), max_concurrent):
                batch_end = min(batch_start + max_concurrent, len(prompts))
                batch_prompts = prompts[batch_start:batch_end]

                logger.info(f"Processing batch {batch_start//max_concurrent + 1}: prompts {batch_start+1}-{batch_end} of {len(prompts)}")

                batch_tasks = [
                    single_request(session, prompt, batch_start + idx)
                    for idx, prompt in enumerate(batch_prompts)
                ]

                batch_results = await asyncio.gather(*batch_tasks)
                all_results.extend(batch_results)

        # Sort by index to maintain order
        all_results.sort(key=lambda x: x[0])
        return [result for _, result in all_results]

    def generate_with_vision(
        self,
        prompt: str,
        image_base64: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """Generate text from prompt and image."""
        if not self._capabilities.vision:
            logger.warning("Vision not available for this provider")
            return None

        try:
            # Determine image type from base64 header or default to jpeg
            if image_base64.startswith("/9j/"):
                media_type = "image/jpeg"
            elif image_base64.startswith("iVBORw"):
                media_type = "image/png"
            else:
                media_type = "image/jpeg"

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]

            payload = {
                "model": self._vision_model or self._model,
                "messages": messages,
                "temperature": temperature if temperature is not None else self._temperature,
                "max_tokens": max_tokens or self._max_tokens,
                "stream": False,
            }

            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
                timeout=self._timeout,
            )

            if response.status_code == 200:
                result = response.json()
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    return message.get("content", "").strip()
            else:
                logger.error(f"Vision generation failed: {response.status_code} - {response.text[:500]}")

            return None

        except requests.exceptions.Timeout:
            logger.error(f"Vision request timed out after {self._timeout} seconds")
            return None
        except Exception as e:
            logger.exception(f"Vision generation error: {e}")
            return None

    def test_connection(self) -> ConnectionTestResult:
        """Test connection and detect capabilities."""
        capabilities = AICapabilities(text=False, vision=False, models=[])
        model_info = None

        # Try to fetch available models
        try:
            response = requests.get(
                f"{self._base_url}/models",
                headers=self._get_headers(),
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                capabilities.models = [m.get("id", m.get("name", "unknown")) for m in models]

                # Check if any model supports vision
                for model in models:
                    model_id = model.get("id", "").lower()
                    # Common vision model patterns
                    if any(v in model_id for v in ["vision", "gpt-4o", "gemma-3", "llava", "bakllava"]):
                        capabilities.vision = True
                        break

        except Exception as e:
            # Models endpoint may not be available (e.g., some local servers)
            logger.debug(f"Could not fetch models list: {e}")

        # Try a simple completion to verify text works
        try:
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers=self._get_headers(),
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": "Say 'ok'"}],
                    "max_tokens": 10,
                    "stream": False,
                },
                timeout=30,
            )

            if response.status_code == 200:
                capabilities.text = True
                result = response.json()
                model_info = {
                    "model": result.get("model"),
                    "usage": result.get("usage"),
                }
            else:
                return ConnectionTestResult(
                    success=False,
                    capabilities=capabilities,
                    error=f"API returned status {response.status_code}: {response.text[:200]}"
                )

        except requests.exceptions.ConnectionError as e:
            return ConnectionTestResult(
                success=False,
                capabilities=capabilities,
                error=f"Connection failed: {str(e)}"
            )
        except requests.exceptions.Timeout:
            return ConnectionTestResult(
                success=False,
                capabilities=capabilities,
                error="Connection timed out"
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                capabilities=capabilities,
                error=f"Error: {str(e)}"
            )

        # If vision setting is explicit, use it
        if self._settings.vision_enabled is not None:
            capabilities.vision = self._settings.vision_enabled

        # Update cached capabilities
        self._capabilities = capabilities

        return ConnectionTestResult(
            success=True,
            capabilities=capabilities,
            model_info=model_info
        )

    def get_capabilities(self) -> AICapabilities:
        """Get cached capabilities."""
        return self._capabilities

    def get_model_info(self) -> Optional[Dict[str, Any]]:
        """Get information about current model."""
        try:
            response = requests.get(
                f"{self._base_url}/models",
                headers=self._get_headers(),
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                # Find the current model
                for model in models:
                    if model.get("id") == self._model or model.get("name") == self._model:
                        return model
                # Return first model if current not found
                if models:
                    return models[0]
            return None

        except Exception:
            return None

    def list_models(self) -> List[str]:
        """List available models."""
        try:
            response = requests.get(
                f"{self._base_url}/models",
                headers=self._get_headers(),
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                return [m.get("id", m.get("name", "unknown")) for m in models]
            return []

        except Exception:
            return []

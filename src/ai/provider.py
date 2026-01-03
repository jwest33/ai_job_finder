"""
Abstract AI Provider Interface

Defines the contract that all AI providers must implement for text and vision generation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AICapabilities:
    """Capabilities of an AI provider."""
    text: bool = True
    vision: bool = False
    models: List[str] = None

    def __post_init__(self):
        if self.models is None:
            self.models = []


@dataclass
class ConnectionTestResult:
    """Result of testing connection to AI provider."""
    success: bool
    capabilities: AICapabilities
    error: Optional[str] = None
    model_info: Optional[Dict[str, Any]] = None


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    All AI providers (OpenAI-compatible, Anthropic, etc.) must implement this interface.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate text completion.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            stop: List of stop sequences
            json_schema: Optional JSON schema to enforce output format

        Returns:
            Generated text or None if request fails
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate JSON response.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            json_schema: Optional JSON schema to enforce output format

        Returns:
            Parsed JSON dict or None if request fails
        """
        pass

    @abstractmethod
    async def generate_batch_async(
        self,
        prompts: List[str],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
        max_concurrent: Optional[int] = None,
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Generate JSON responses for multiple prompts concurrently.

        Args:
            prompts: List of prompts to process
            temperature: Sampling temperature
            max_tokens: Maximum tokens per response
            json_schema: Optional JSON schema to enforce output format
            max_concurrent: Maximum concurrent requests

        Returns:
            List of parsed JSON dicts (or None for failed requests)
        """
        pass

    @abstractmethod
    def generate_with_vision(
        self,
        prompt: str,
        image_base64: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generate text from prompt and image.

        Args:
            prompt: The text prompt
            image_base64: Base64-encoded image data
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text or None if request fails or vision not supported
        """
        pass

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """
        Test connection to the AI provider and detect capabilities.

        Returns:
            ConnectionTestResult with success status and capabilities
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> AICapabilities:
        """
        Get cached capabilities of this provider.

        Returns:
            AICapabilities with text/vision support and available models
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the current model.

        Returns:
            Model info dict or None if unavailable
        """
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """
        List available models from the provider.

        Returns:
            List of model names/IDs
        """
        pass

    @property
    @abstractmethod
    def server_url(self) -> str:
        """Get the server/API URL."""
        pass

    @property
    @abstractmethod
    def has_vision(self) -> bool:
        """Check if vision capabilities are available."""
        pass

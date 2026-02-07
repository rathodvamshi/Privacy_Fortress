"""
Groq Client - LLM integration with Groq API
Fast inference with Llama 3.3 and Mixtral models
"""
import asyncio
from typing import List, Dict, Optional, AsyncGenerator
from groq import Groq, AsyncGroq
import logging

from ..core.config import settings
from ..core.exceptions import LLMException
from .prompt_shield import PromptShield, get_prompt_shield
from .validator import ResponseValidator, get_response_validator

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Groq API client for LLM inference
    
    Features:
    - Async streaming support
    - Multiple model options
    - Integrated prompt shield
    - Response validation
    """
    
    # Available models
    MODELS = {
        'fast': 'llama-3.1-8b-instant',        # Fastest
        'balanced': 'llama-3.3-70b-versatile', # Best quality
        'mixtral': 'mixtral-8x7b-32768',       # Long context
        'small': 'llama-3.2-3b-preview',       # Smallest
    }
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize Groq client
        
        Args:
            api_key: Groq API key (defaults to env variable)
            model: Model to use (defaults to balanced)
        """
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        
        if not self.api_key:
            raise LLMException("Groq API key not configured")
        
        # Initialize clients
        self.sync_client = Groq(api_key=self.api_key)
        self.async_client = AsyncGroq(api_key=self.api_key)
        
        # Initialize protection layers
        self.prompt_shield = get_prompt_shield()
        self.validator = get_response_validator()
        
        logger.info(f"Groq client initialized with model: {self.model}")
    
    def chat(
        self,
        message: str,
        history: List[Dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> str:
        """
        Synchronous chat completion
        
        Args:
            message: User message (should be masked)
            history: Previous conversation messages
            temperature: Creativity parameter
            max_tokens: Maximum response length
            
        Returns:
            Assistant response (masked)
        """
        try:
            # Check for jailbreak attempts
            is_jailbreak, matched = self.prompt_shield.is_jailbreak_attempt(message)
            if is_jailbreak:
                logger.warning(f"Jailbreak attempt blocked: {matched}")
                return self.prompt_shield.get_blocked_response()
            
            # Sanitize input
            sanitized, blocked = self.prompt_shield.sanitize_input(message)
            if blocked:
                logger.warning(f"Blocked phrases removed: {blocked}")
            
            # Build messages
            if history:
                messages = self.prompt_shield.build_conversation(history, sanitized)
            else:
                messages = self.prompt_shield.wrap_message(sanitized)
            
            # Call Groq API
            response = self.sync_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            assistant_message = response.choices[0].message.content
            
            # Validate response
            is_valid, leaks = self.validator.validate(assistant_message)
            if not is_valid:
                logger.warning(f"Potential PII leakage detected, sanitizing response")
                assistant_message = self.validator.sanitize(assistant_message, leaks)
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            raise LLMException(f"Failed to get LLM response: {str(e)}")
    
    async def chat_async(
        self,
        message: str,
        history: List[Dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> str:
        """
        Asynchronous chat completion
        
        Args:
            message: User message (should be masked)
            history: Previous conversation messages
            temperature: Creativity parameter
            max_tokens: Maximum response length
            
        Returns:
            Assistant response (masked)
        """
        try:
            # Check for jailbreak attempts
            is_jailbreak, matched = self.prompt_shield.is_jailbreak_attempt(message)
            if is_jailbreak:
                logger.warning(f"Jailbreak attempt blocked: {matched}")
                return self.prompt_shield.get_blocked_response()
            
            # Sanitize input
            sanitized, blocked = self.prompt_shield.sanitize_input(message)
            
            # Build messages
            if history:
                messages = self.prompt_shield.build_conversation(history, sanitized)
            else:
                messages = self.prompt_shield.wrap_message(sanitized)
            
            # Call Groq API
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            assistant_message = response.choices[0].message.content
            
            # Validate response
            is_valid, leaks = self.validator.validate(assistant_message)
            if not is_valid:
                assistant_message = self.validator.sanitize(assistant_message, leaks)
            
            return assistant_message
            
        except Exception as e:
            logger.error(f"Async chat completion failed: {e}")
            raise LLMException(f"Failed to get LLM response: {str(e)}")
    
    async def chat_stream(
        self,
        message: str,
        history: List[Dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion
        
        Args:
            message: User message (should be masked)
            history: Previous conversation messages
            temperature: Creativity parameter
            max_tokens: Maximum response length
            
        Yields:
            Response chunks
        """
        try:
            # Check for jailbreak attempts
            is_jailbreak, matched = self.prompt_shield.is_jailbreak_attempt(message)
            if is_jailbreak:
                yield self.prompt_shield.get_blocked_response()
                return
            
            # Sanitize input
            sanitized, _ = self.prompt_shield.sanitize_input(message)
            
            # Build messages
            if history:
                messages = self.prompt_shield.build_conversation(history, sanitized)
            else:
                messages = self.prompt_shield.wrap_message(sanitized)
            
            # Stream from Groq API
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"Stream chat failed: {e}")
            yield f"Error: {str(e)}"
    
    def get_model_info(self) -> Dict:
        """Get current model information"""
        return {
            'model': self.model,
            'available_models': self.MODELS,
            'provider': 'Groq',
        }
    
    def switch_model(self, model_key: str):
        """
        Switch to a different model
        
        Args:
            model_key: Key from MODELS dict (fast, balanced, mixtral, small)
        """
        if model_key in self.MODELS:
            self.model = self.MODELS[model_key]
            logger.info(f"Switched to model: {self.model}")
        else:
            raise LLMException(f"Unknown model key: {model_key}")
    
    async def health_check(self) -> Dict:
        """Check Groq API health"""
        try:
            start = asyncio.get_event_loop().time()
            
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            
            latency = (asyncio.get_event_loop().time() - start) * 1000
            
            return {
                'status': 'healthy',
                'model': self.model,
                'latency_ms': round(latency, 2)
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }


# Singleton
_groq_client = None

def get_groq_client() -> GroqClient:
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client

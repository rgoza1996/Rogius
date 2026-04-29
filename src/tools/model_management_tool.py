"""
Model Management Tool - Switch between local AI models and external APIs for Rogius.

Supports:
- List available local models (LM Studio, Ollama)
- Switch active model
- Test model connectivity
- Configure fallback providers
- Show current model status
"""

import os
import json
import aiohttp
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
from .tool_interface import Tool, Action, ActionType, ToolResult
from .tool_registry import tool


@tool(ActionType.MODEL_MANAGE)
class ModelManagementTool(Tool):
    """
    Tool for managing AI model connections in Rogius.
    
    Designed for local AI workflows with optional external API fallback.
    Supports LM Studio, Ollama, and OpenAI-compatible endpoints.
    """
    
    DEFAULT_CONFIG_PATH = "rogius.config.json"
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.MODEL_MANAGE
    
    async def execute(self, action: Action, env_context: dict) -> ToolResult:
        """
        Execute a model management operation.
        
        Args:
            action: Action with payload containing operation and parameters
            env_context: Dict with context including config path
            
        Returns:
            ToolResult with operation results
        """
        payload = action.payload
        operation = payload.get("operation", "")
        working_dir = env_context.get("working_directory", os.getcwd())
        config_path = payload.get("config_path") or os.path.join(working_dir, self.DEFAULT_CONFIG_PATH)
        
        if not operation:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error="No model operation specified"
            )
        
        try:
            if operation == "status":
                result = await self._op_status(config_path, payload)
            elif operation == "list":
                result = await self._op_list(config_path, payload)
            elif operation == "switch":
                result = await self._op_switch(config_path, payload)
            elif operation == "test":
                result = await self._op_test(config_path, payload)
            elif operation == "configure":
                result = await self._op_configure(config_path, payload)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    artifacts={},
                    error=f"Unknown operation: {operation}"
                )
            
            return result
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error=f"Model management failed: {str(e)}"
            )
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return default config
            return {
                "chatEndpoint": "http://localhost:1234/v1/chat/completions",
                "chatApiKey": "",
                "chatModel": "local-model",
                "chatContextLength": 4096,
                "ttsEndpoint": "",
                "ttsApiKey": "",
                "ttsVoice": "",
                "autoPlayAudio": False
            }
    
    def _save_config(self, config_path: str, config: dict) -> bool:
        """Save configuration to file."""
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception:
            return False
    
    async def _op_status(self, config_path: str, payload: dict) -> ToolResult:
        """Get current model status."""
        config = self._load_config(config_path)
        endpoint = config.get("chatEndpoint", "")
        model = config.get("chatModel", "")
        context_length = config.get("chatContextLength", 4096)
        
        # Determine provider type
        if "localhost" in endpoint or "127.0.0.1" in endpoint:
            provider_type = "local"
            provider_name = self._detect_local_provider(endpoint)
        elif "openai" in endpoint:
            provider_type = "external"
            provider_name = "OpenAI"
        elif "anthropic" in endpoint or "claude" in endpoint:
            provider_type = "external"
            provider_name = "Anthropic"
        elif "groq" in endpoint:
            provider_type = "external"
            provider_name = "Groq"
        else:
            provider_type = "external"
            provider_name = "Custom API"
        
        # Check connectivity
        connectivity = await self._test_endpoint(endpoint, config.get("chatApiKey"))
        
        return ToolResult(
            success=True,
            output=f"Current model: {model} via {provider_name} ({provider_type})",
            artifacts={
                "operation": "status",
                "config_path": config_path,
                "endpoint": endpoint,
                "model": model,
                "context_length": context_length,
                "provider_type": provider_type,
                "provider_name": provider_name,
                "has_api_key": bool(config.get("chatApiKey")),
                "connectivity": connectivity,
                "reachable": connectivity.get("reachable", False)
            }
        )
    
    def _detect_local_provider(self, endpoint: str) -> str:
        """Detect which local provider is being used."""
        if ":1234" in endpoint:
            return "LM Studio"
        elif ":11434" in endpoint:
            return "Ollama"
        elif "llama.cpp" in endpoint:
            return "llama.cpp"
        else:
            return "Local Server"
    
    async def _op_list(self, config_path: str, payload: dict) -> ToolResult:
        """List available models from endpoint."""
        config = self._load_config(config_path)
        endpoint = config.get("chatEndpoint", "")
        
        # Try to get models from endpoint
        models = await self._fetch_models(endpoint, config.get("chatApiKey"))
        
        # If no models from endpoint, provide defaults based on provider
        if not models:
            if "ollama" in endpoint or ":11434" in endpoint:
                models = [
                    {"id": "llama3.2", "name": "Llama 3.2", "size": "3B"},
                    {"id": "llama3.1", "name": "Llama 3.1", "size": "8B"},
                    {"id": "qwen2.5", "name": "Qwen 2.5", "size": "7B"},
                    {"id": "mistral", "name": "Mistral", "size": "7B"},
                ]
            elif "localhost" in endpoint or "127.0.0.1" in endpoint:
                models = [
                    {"id": "local-model", "name": "Current Local Model", "context": 4096}
                ]
        
        return ToolResult(
            success=True,
            output=f"Found {len(models)} model(s) at {endpoint}",
            artifacts={
                "operation": "list",
                "models": models,
                "endpoint": endpoint,
                "count": len(models)
            }
        )
    
    async def _op_switch(self, config_path: str, payload: dict) -> ToolResult:
        """Switch to a different model."""
        model = payload.get("model", "")
        endpoint = payload.get("endpoint", "")
        api_key = payload.get("api_key", "")
        
        if not model and not endpoint:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error="Must specify model or endpoint to switch"
            )
        
        config = self._load_config(config_path)
        
        old_model = config.get("chatModel", "")
        old_endpoint = config.get("chatEndpoint", "")
        
        if model:
            config["chatModel"] = model
        if endpoint:
            config["chatEndpoint"] = endpoint
        if api_key:
            config["chatApiKey"] = api_key
        
        saved = self._save_config(config_path, config)
        
        if not saved:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error=f"Failed to save configuration to {config_path}"
            )
        
        # Test new configuration
        connectivity = await self._test_endpoint(
            config.get("chatEndpoint"),
            config.get("chatApiKey")
        )
        
        return ToolResult(
            success=True,
            output=f"Switched from {old_model} to {config['chatModel']}",
            artifacts={
                "operation": "switch",
                "previous_model": old_model,
                "previous_endpoint": old_endpoint,
                "new_model": config["chatModel"],
                "new_endpoint": config["chatEndpoint"],
                "connectivity": connectivity,
                "reachable": connectivity.get("reachable", False)
            }
        )
    
    async def _op_test(self, config_path: str, payload: dict) -> ToolResult:
        """Test endpoint connectivity."""
        config = self._load_config(config_path)
        endpoint = payload.get("endpoint") or config.get("chatEndpoint")
        api_key = payload.get("api_key") or config.get("chatApiKey")
        
        connectivity = await self._test_endpoint(endpoint, api_key)
        
        return ToolResult(
            success=connectivity.get("reachable", False),
            output=f"Endpoint {'reachable' if connectivity.get('reachable') else 'unreachable'}",
            artifacts={
                "operation": "test",
                "endpoint": endpoint,
                "connectivity": connectivity
            },
            error=connectivity.get("error") if not connectivity.get("reachable") else None
        )
    
    async def _test_endpoint(self, endpoint: str, api_key: str) -> dict:
        """Test if an endpoint is reachable."""
        if not endpoint:
            return {"reachable": False, "error": "No endpoint specified"}
        
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Try to get models or send a minimal request
            async with aiohttp.ClientSession() as session:
                # Try /models endpoint first
                models_url = endpoint.replace("/chat/completions", "/models")
                
                try:
                    async with session.get(models_url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            return {"reachable": True, "latency_ms": 0}
                except Exception:
                    pass
                
                # Try a minimal chat completion
                test_payload = {
                    "model": "test",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
                
                async with session.post(endpoint, headers=headers, json=test_payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    # Any response (even error) means endpoint exists
                    return {
                        "reachable": True,
                        "status": resp.status,
                        "error": None if resp.status == 200 else f"HTTP {resp.status}"
                    }
                    
        except asyncio.TimeoutError:
            return {"reachable": False, "error": "Connection timeout"}
        except aiohttp.ClientError as e:
            return {"reachable": False, "error": f"Connection error: {str(e)}"}
        except Exception as e:
            return {"reachable": False, "error": str(e)}
    
    async def _fetch_models(self, endpoint: str, api_key: str) -> list:
        """Fetch available models from endpoint."""
        try:
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            models_url = endpoint.replace("/chat/completions", "/models")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(models_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get("data", [])
                        return [{"id": m.get("id"), "name": m.get("id")} for m in models]
                    return []
        except Exception:
            return []
    
    async def _op_configure(self, config_path: str, payload: dict) -> ToolResult:
        """Configure model settings."""
        config = self._load_config(config_path)
        
        # Update settings
        if "context_length" in payload:
            config["chatContextLength"] = payload["context_length"]
        if "temperature" in payload:
            config["temperature"] = payload["temperature"]
        if "max_tokens" in payload:
            config["max_tokens"] = payload["max_tokens"]
        
        saved = self._save_config(config_path, config)
        
        return ToolResult(
            success=saved,
            output="Configuration updated" if saved else "Failed to save configuration",
            artifacts={
                "operation": "configure",
                "config": config,
                "updated_settings": [k for k in payload.keys() if k != "operation"]
            },
            error=None if saved else "Save failed"
        )
    
    def verify(self, action: Action, result: ToolResult) -> dict:
        """Verify model management results."""
        artifacts = result.artifacts
        operation = artifacts.get("operation", "")
        
        verification = {
            "tool_verified": result.success,
            "operation": operation
        }
        
        if operation == "switch":
            verification["new_model_set"] = bool(artifacts.get("new_model"))
            verification["endpoint_reachable"] = artifacts.get("reachable", False)
        elif operation == "test":
            verification["endpoint_reachable"] = artifacts.get("reachable", False)
        
        return verification
    
    def classify_failure(self, result: ToolResult) -> str:
        """Classify model management failures."""
        error = result.error or ""
        error_lower = error.lower()
        
        if "timeout" in error_lower:
            return "connection_timeout"
        elif "unreachable" in error_lower or "connection" in error_lower:
            return "endpoint_unreachable"
        elif "unauthorized" in error_lower or "401" in error_lower:
            return "invalid_api_key"
        elif "not found" in error_lower or "404" in error_lower:
            return "endpoint_not_found"
        elif "permission" in error_lower:
            return "config_write_failed"
        
        return "unknown"
    
    def apply_failure_fix(self, action: Action, hint: str) -> Optional[Action]:
        """Apply fixes for common model management failures."""
        payload = action.payload.copy()
        operation = payload.get("operation", "")
        
        if hint == "endpoint_unreachable" and operation == "switch":
            # Try default local endpoint
            payload["endpoint"] = "http://localhost:1234/v1/chat/completions"
            return Action(
                type=action.type,
                payload=payload,
                description=f"{action.description} (fix: using default local endpoint)",
                timeout=action.timeout
            )
        
        elif hint == "invalid_api_key":
            # Clear API key and try without
            payload["api_key"] = ""
            return Action(
                type=action.type,
                payload=payload,
                description=f"{action.description} (fix: trying without API key)",
                timeout=action.timeout
            )
        
        return None
    
    def get_schema(self) -> dict:
        """Return schema for model_manage action."""
        return {
            "type": "model_manage",
            "description": "Manage AI model connections - switch between local and external providers",
            "payload_schema": {
                "operation": "string - One of: status, list, switch, test, configure",
                "config_path": "string - Path to config file (optional)",
                # For switch operation
                "model": "string - Model ID to switch to",
                "endpoint": "string - API endpoint URL",
                "api_key": "string - API key for external providers",
                # For configure operation
                "context_length": "integer - Max context length",
                "temperature": "float - Sampling temperature",
                "max_tokens": "integer - Max tokens per response"
            },
            "operations": {
                "status": "Show current model configuration and connectivity",
                "list": "List available models from current endpoint",
                "switch": "Switch to a different model/endpoint",
                "test": "Test endpoint connectivity",
                "configure": "Update model configuration settings"
            },
            "failure_hints": ["connection_timeout", "endpoint_unreachable", "invalid_api_key", "endpoint_not_found", "config_write_failed"],
            "supported_providers": {
                "local": ["LM Studio", "Ollama", "llama.cpp"],
                "external": ["OpenAI", "Anthropic", "Groq", "Custom OpenAI-compatible"]
            }
        }
    
    def get_examples(self) -> list[dict]:
        """Return example model_manage actions."""
        return [
            {
                "operation": "status"
            },
            {
                "operation": "list"
            },
            {
                "operation": "switch",
                "model": "qwen2.5",
                "endpoint": "http://localhost:1234/v1/chat/completions"
            },
            {
                "operation": "test",
                "endpoint": "http://localhost:11434/v1/chat/completions"
            },
            {
                "operation": "configure",
                "context_length": 8192,
                "temperature": 0.7
            }
        ]

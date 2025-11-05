"""Centralized LLM configuration for Strands agents.

Exports a shared Ollama model instance so all agents/tools use the same
local model and avoid relying on external credentials.
"""

from strands.models.ollama import OllamaModel


# Shared Ollama model (local server)
ollama_model = OllamaModel(
    host="http://localhost:11434",
    model_id="qwen3:14b",
)


"""
LLM wrapper — swap providers by changing config.ACTIVE_PROVIDER.
Supported: groq | openai | anthropic
"""

from src.config import (
    ACTIVE_PROVIDER, ACTIVE_MODEL, MAX_TOKENS_LLM,
    GROQ_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
)


def _build_client():
    if ACTIVE_PROVIDER in ("groq", "openai"):
        from openai import OpenAI
        if ACTIVE_PROVIDER == "groq":
            return OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        return OpenAI(api_key=OPENAI_API_KEY)

    if ACTIVE_PROVIDER == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    raise ValueError(f"Unknown provider: {ACTIVE_PROVIDER}")


_client = _build_client()


def llm_chat(system_prompt: str, messages: list) -> str:
    """
    Unified chat call.

    Args:
        system_prompt: instruction for the model
        messages:      list of {"role": "user"|"assistant", "content": str}

    Returns:
        Model's reply as a plain string.
    """
    if ACTIVE_PROVIDER in ("groq", "openai"):
        response = _client.chat.completions.create(
            model=ACTIVE_MODEL,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            max_tokens=MAX_TOKENS_LLM,
        )
        return response.choices[0].message.content

    if ACTIVE_PROVIDER == "anthropic":
        response = _client.messages.create(
            model=ACTIVE_MODEL,
            max_tokens=MAX_TOKENS_LLM,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    raise ValueError(f"Unknown provider: {ACTIVE_PROVIDER}")

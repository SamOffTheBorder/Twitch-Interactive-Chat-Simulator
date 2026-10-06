from openai import OpenAI

import config

_local: OpenAI | None = None
_openrouter: OpenAI | None = None


def _get_local() -> OpenAI | None:
    if not config.LOCAL_LLM_MODEL:
        return None
    global _local
    if _local is None:
        _local = OpenAI(base_url=config.LOCAL_LLM_URL, api_key="ollama")
    return _local


def _get_openrouter() -> OpenAI:
    global _openrouter
    if _openrouter is None:
        _openrouter = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.OPENROUTER_API_KEY,
        )
    return _openrouter


def complete(
    system: str,
    user: str,
    max_tokens: int = 40,
    temperature: float = 1.0,
    frequency_penalty: float = 0.4,
    presence_penalty: float = 0.3,
) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    kwargs = dict(
        max_tokens=max_tokens,
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        messages=messages,
    )

    # 1. Local Ollama (primary)
    local = _get_local()
    if local:
        try:
            resp = local.chat.completions.create(model=config.LOCAL_LLM_MODEL, **kwargs)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"[LLM] Local failed ({e}), trying OpenRouter...")

    # 2. OpenRouter primary model (small, persona-following — best for casual chat)
    if config.OPENROUTER_MODEL:
        try:
            resp = _get_openrouter().chat.completions.create(model=config.OPENROUTER_MODEL, **kwargs)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"[LLM] OpenRouter primary failed ({e}), trying fallback...")

    # 3. OpenRouter fallback model
    try:
        resp = _get_openrouter().chat.completions.create(model=config.OPENROUTER_FALLBACK_MODEL, **kwargs)
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[LLM] OpenRouter fallback failed ({e})")

    return ""

"""Gemini adapter; citations are validated by the answer pipeline after generation."""

import json
import time

from .config import get_settings
from .providers import ProviderError


def gemini_generate(system, question, evidence, history=None):
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ProviderError("Gemini needs GEMINI_API_KEY. Configure it on the server or use offline answers.")
    try:
        from google import genai
        from google.genai import types
        from google.genai.errors import APIError
        from .answers import GeneratedAnswer
    except ImportError:
        raise ProviderError("Install the google-genai package to enable Gemini.") from None
    for attempt in range(3):
        try:
            with genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(
                    timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)
                ),
            ) as client:
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=json.dumps(
                        {
                            "question": question,
                            "evidence": evidence,
                            "conversation_context_untrusted": history or [],
                        }
                    ),
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        response_schema=GeneratedAnswer,
                        temperature=0,
                    ),
                )
            usage = response.usage_metadata
            return response.text, {
                "prompt_tokens": usage.prompt_token_count or 0,
                "completion_tokens": usage.candidates_token_count or 0,
            } if usage else {}
        except APIError as error:
            if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(0.5 * 2**attempt)
                continue
            raise ProviderError(
                "Gemini could not answer. Check the API key, model availability and quota."
            ) from None
        except Exception:
            raise ProviderError("Gemini request failed or timed out. Please try again.") from None
    raise ProviderError("Gemini is temporarily unavailable.")

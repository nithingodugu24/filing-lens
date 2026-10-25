"""Gemini adapter; citations are validated by the answer pipeline after generation."""

import json
import time

from .config import get_settings
from .providers import ProviderError


def gemini_generate(system, question, evidence, history=None, on_delta=None, cancelled=None):
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
                generate = (
                    client.models.generate_content_stream if on_delta else client.models.generate_content
                )
                response = generate(
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
                if on_delta:
                    from .answer_progress import check_cancelled

                    parts, usage = [], None
                    for chunk in response:
                        check_cancelled(cancelled)
                        if chunk.text:
                            parts.append(chunk.text)
                            on_delta(chunk.text)
                        if chunk.usage_metadata:
                            usage = chunk.usage_metadata
                    return "".join(parts), {
                        "prompt_tokens": usage.prompt_token_count or 0,
                        "completion_tokens": usage.candidates_token_count or 0,
                    } if usage else {}
            usage = response.usage_metadata
            return response.text, {
                "prompt_tokens": usage.prompt_token_count or 0,
                "completion_tokens": usage.candidates_token_count or 0,
            } if usage else {}
        except APIError as error:
            if not on_delta and error.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(0.5 * 2**attempt)
                continue
            raise ProviderError(
                "Gemini could not answer. Check the API key, model availability and quota."
            ) from None
        except Exception as error:
            from .answer_progress import StreamCancelled

            if isinstance(error, StreamCancelled):
                raise
            raise ProviderError("Gemini request failed or timed out. Please try again.") from None
    raise ProviderError("Gemini is temporarily unavailable.")

import logging

logger = logging.getLogger(__name__)


import os
from openai import OpenAI
from django.core.cache import cache


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(
        self,
        prompt: str,
        model: str = "gpt-5-mini",
        max_tokens: int = 300,
        use_cache: bool = True,
    ) -> str:

        cache_key = f"openai:{model}:{hash(prompt)}"

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        response = self.client.responses.create(
            model=model,
            input=prompt,
            max_output_tokens=max_tokens,
        )

        # 🔥 SAFE extraction
        output = getattr(response, "output_text", None)

        if not output:
            raise ValueError(f"No output returned by OpenAI: {response}")

        if use_cache:
            cache.set(cache_key, output, timeout=60 * 60 * 24)

        return output

import logging
import os
import mimetypes
from django.core.cache import cache
from openai import OpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate(
        self,
        prompt: str,
        model: str = "gpt-4o",
        max_tokens: int = 300,
        use_cache: bool = True,
    ) -> str:

        cache_key = f"openai:{model}:{hash(prompt)}"

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )

        output = response.choices[0].message.content

        if not output:
            raise ValueError(f"No output returned by OpenAI: {response}")

        if use_cache:
            cache.set(cache_key, output, timeout=60 * 60 * 24)

        return output

    def upload_file(self, path: str) -> str:
        """Upload a local file to OpenAI and return the file ID."""
        content_type, _ = mimetypes.guess_type(path)
        mime_type = content_type or "application/octet-stream"

        with open(path, "rb") as f:
            file_bytes = f.read()

        response = self.client.uploads.create(
            file=file_bytes,
            filename=os.path.basename(path),
            mime_type=mime_type,
            purpose="responses",
        )

        file_id = getattr(response, "id", None) or getattr(response, "file_id", None)
        if not file_id:
            raise ValueError(f"Failed to upload file to OpenAI: {response}")

        return file_id

    def generate_with_images(
        self,
        prompt: str,
        image_inputs: list,
        model: str = "gpt-4o",
        max_tokens: int = 1200,
        use_cache: bool = True,
    ) -> str:
        cache_key = f"openai:{model}:{hash(prompt)}:{hash(str(image_inputs))}"

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        # Build content array with text and images
        content = [{"type": "text", "text": prompt}]
        content.extend(image_inputs)

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
        )

        output = response.choices[0].message.content
        if not output:
            raise ValueError(f"No output returned by OpenAI image analysis: {response}")

        if use_cache:
            cache.set(cache_key, output, timeout=60 * 60 * 24)

        return output

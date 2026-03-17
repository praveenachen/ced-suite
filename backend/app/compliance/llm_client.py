from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseLLMClient(ABC):
    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        raise NotImplementedError


class NullLLMClient(BaseLLMClient):
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        return {"compliance_gaps": []}


class OpenAICompatibleLLMClient(BaseLLMClient):
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            return {"compliance_gaps": []}

        from openai import OpenAI

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re

from typing import Any, Dict, List, Optional

# Load .env automatically
try:
	from dotenv import load_dotenv
	load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
except Exception:
	pass

try:
	import google.generativeai as genai
except Exception:  # pragma: no cover - import guarded for optional dependency
	genai = None

logger = logging.getLogger(__name__)
_GEMINI_CONFIGURED = False


def gemini_sdk_available() -> bool:
	return genai is not None or importlib.util.find_spec("google.generativeai") is not None


def get_gemini_api_key() -> Optional[str]:
	return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def configure_gemini() -> Optional[str]:
	global _GEMINI_CONFIGURED
	if _GEMINI_CONFIGURED:
		return get_gemini_api_key()

	api_key = get_gemini_api_key()
	if not api_key:
		return None

	if genai is None:
		return None

	genai.configure(api_key=api_key)
	_GEMINI_CONFIGURED = True
	return api_key


def _parse_json(text: str) -> Dict[str, Any]:
	try:
		return json.loads(text)
	except Exception:
		pass

	match = re.search(r"\{.*\}", text, flags=re.S)
	if match:
		return json.loads(match.group(0))

	match = re.search(r"\[.*\]", text, flags=re.S)
	if match:
		return json.loads(match.group(0))

	raise RuntimeError("Gemini response did not contain valid JSON")


def generate_json(
	*,
	model: str,
	system_msg: str,
	user_msg: str,
	temperature: float = 0.1,
) -> Dict[str, Any]:
	if genai is None:
		raise RuntimeError("google-generativeai is not installed")

	api_key = configure_gemini()
	if not api_key:
		raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")

	gen_model = genai.GenerativeModel(model, system_instruction=system_msg)
	response = gen_model.generate_content(
		user_msg,
		generation_config=genai.GenerationConfig(temperature=temperature),
	)

	text = (getattr(response, "text", None) or "").strip()
	if not text and hasattr(response, "candidates"):
		try:
			text = response.candidates[0].content.parts[0].text
		except Exception:
			text = ""

	return _parse_json(text)


def embed_texts(
	*,
	texts: List[str],
	model: str,
	task_type: str,
) -> List[List[float]]:
	if genai is None:
		raise RuntimeError("google-generativeai is not installed")

	api_key = configure_gemini()
	if not api_key:
		raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY")

	embeddings: List[List[float]] = []
	for text in texts:
		resp = genai.embed_content(
			model=model,
			content=text,
			task_type=task_type,
		)
		if isinstance(resp, dict):
			emb = resp.get("embedding")
		else:
			emb = getattr(resp, "embedding", None)

		if emb is None:
			raise RuntimeError("Gemini embedding response missing embedding")

		embeddings.append(list(emb))

	return embeddings

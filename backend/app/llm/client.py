from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

# Load .env automatically
try:
	from dotenv import load_dotenv
	load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
except Exception:
	pass

try:
	import openai
except Exception:  # pragma: no cover - import guarded for optional dependency
	openai = None

logger = logging.getLogger(__name__)


def openai_sdk_available() -> bool:
	try:
		import openai
		return True
	except ImportError:
		return False


def get_openai_api_key() -> Optional[str]:
	return os.getenv("OPENAI_API_KEY")


def configure_openai() -> Optional[str]:
	"""Configure OpenAI client and return API key."""
	api_key = get_openai_api_key()
	if not api_key:
		return None

	if openai is None:
		return None

	# OpenAI client configures itself automatically from environment
	return api_key




def generate_json(
	*,
	model: str,
	system_msg: str,
	user_msg: str,
	temperature: float = 0.1,
) -> Dict[str, Any]:
	"""Generate JSON response using OpenAI Chat Completions."""
	if openai is None:
		raise RuntimeError("openai package is not installed")

	api_key = configure_openai()
	if not api_key:
		raise RuntimeError("Missing OPENAI_API_KEY")

	try:
		client = openai.OpenAI(api_key=api_key)
		response = client.chat.completions.create(
			model=model,
			messages=[
				{"role": "system", "content": system_msg},
				{"role": "user", "content": user_msg}
			],
			temperature=temperature,
			response_format={"type": "json_object"}
		)

		content = response.choices[0].message.content
		if not content:
			raise RuntimeError("OpenAI returned empty response")

		return json.loads(content)
	except json.JSONDecodeError as e:
		raise RuntimeError(f"Failed to parse OpenAI JSON response: {e}")
	except Exception as e:
		raise RuntimeError(f"OpenAI API error: {e}")


def embed_texts(
	*,
	texts: List[str],
	model: str,
	task_type: str = None,  # OpenAI doesn't use task_type, kept for compatibility
) -> List[List[float]]:
	"""Generate embeddings using OpenAI Embeddings API."""
	if openai is None:
		raise RuntimeError("openai package is not installed")

	api_key = configure_openai()
	if not api_key:
		raise RuntimeError("Missing OPENAI_API_KEY")

	# Use default OpenAI embedding model if Gemini model specified
	if model.startswith("models/embedding-001") or model.startswith("gemini-embedding"):
		model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")

	try:
		client = openai.OpenAI(api_key=api_key)

		# Process texts in batches to respect OpenAI's limits (max 2048 inputs)
		embeddings: List[List[float]] = []
		batch_size = 2048

		for i in range(0, len(texts), batch_size):
			batch_texts = texts[i:i + batch_size]

			response = client.embeddings.create(
				model=model,
				input=batch_texts
			)

			# Extract embeddings from response
			batch_embeddings = [emb.embedding for emb in response.data]
			embeddings.extend(batch_embeddings)

		return embeddings
	except Exception as e:
		raise RuntimeError(f"OpenAI Embeddings API error: {e}")

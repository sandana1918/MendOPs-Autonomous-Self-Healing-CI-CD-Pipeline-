import logging
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger("patchforge.agent")


class PatchResponse(BaseModel):
    explanation: str = Field(min_length=1)
    patched_code: str = Field(min_length=1)


SYSTEM_PROMPT = """
You are PatchForge AI. Return only valid structured data.
Return a JSON object with exactly: explanation, patched_code.
Patch only the production code block. Do not include markdown fences.
Keep the existing public API intact. Do not import network, filesystem,
process, reflection, or environment-access modules.
"""


async def generate_patch(
    issue_title: str,
    issue_body: str,
    faulty_code: str,
) -> Optional[PatchResponse]:
    api_key = settings.AI_API_KEY or settings.OPENAI_API_KEY
    if not api_key:
        logger.error("AI_API_KEY or OPENAI_API_KEY missing")
        return None

    client_kwargs = {"api_key": api_key}
    if settings.AI_BASE_URL:
        client_kwargs["base_url"] = settings.AI_BASE_URL
    client = AsyncOpenAI(**client_kwargs)
    prompt = (
        f"Issue title:\n{issue_title}\n\n"
        f"Issue body:\n{issue_body}\n\n"
        f"Current code and tests:\n{faulty_code}\n"
    )

    try:
        response = await client.chat.completions.create(
            model=settings.MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=settings.LLM_TEMPERATURE,
        )
        content = response.choices[0].message.content or "{}"
        return PatchResponse.model_validate_json(content)
    except Exception:
        logger.exception("OpenAI patch generation failed")
        if settings.DEMO_PATCH_FALLBACK:
            return _demo_patch(faulty_code)
        return None


def _demo_patch(faulty_code: str) -> Optional[PatchResponse]:
    if "calculate_average_rating" not in faulty_code:
        return None

    return PatchResponse(
        explanation="Offline demo fallback: handle an empty ratings list by returning 0.0 before dividing.",
        patched_code=(
            "def calculate_average_rating(ratings_list):\n"
            "    \"\"\"Calculates user ratings with an empty-list fallback.\"\"\"\n"
            "    if not ratings_list:\n"
            "        return 0.0\n"
            "    return sum(ratings_list) / len(ratings_list)\n"
        ),
    )

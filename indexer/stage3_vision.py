"""Stage 3 — Vision: three-pass picture summarization (caption → structured → synthesis)."""

import logging
import sys

from indexer.config import (
    VLM_CAPTION_MAX_TOKENS,
    VLM_MAX_TOKENS,
    VLM_TEMPERATURE,
    VLM_SYNTHESIS_MAX_TOKENS,
)
from indexer.vision_utils import (
    VLM_CAPTION_PROMPT,
    VLM_STRUCTURED_SYSTEM_PROMPT,
    VLM_STRUCTURED_PROMPT,
    VLM_SYNTHESIS_SYSTEM_PROMPT,
    VLM_SYNTHESIS_PROMPT_TEMPLATE,
    _size_guard,
    _strip_preamble,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def summarize_pictures(pic_info: list, vlm, llm) -> dict:
    """
    Run three VLM/LLM passes over each picture and return a vision_map.

    Pass 1 — caption      : short description, temperature=0.0, VLM_CAPTION_MAX_TOKENS
    Pass 2 — structured   : typed analysis,    VLM_TEMPERATURE,  VLM_MAX_TOKENS
    Pass 3 — synthesis    : coherent paragraph via LLM, VLM_SYNTHESIS_MAX_TOKENS

    Parameters
    ----------
    pic_info : list of picture dicts from stage1_parse
    vlm      : VLMInference instance
    llm      : LLMInference instance

    Returns
    -------
    vision_map : {element_id: {"caption": str, "structured": str, "synthesis": str}}
    """
    log.info(f"Summarizing {len(pic_info)} pictures using VLM/LLM")
    vision_map: dict[str, dict] = {}

    for pic in pic_info:
        element_id = pic["element_id"]
        image_path = pic.get("image_path")

        log.info(f"Processing picture: {element_id}")
        if not image_path:
            # No image bytes — fall back to the docling caption if present
            fallback = pic.get("caption", "")
            vision_map[element_id] = {
                "caption": fallback,
                "structured": "",
                "synthesis": fallback,
            }
            log.info(f"No image path for picture: {element_id}, using fallback")
            continue

        # --- Pass 1: short caption ---
        try:
            log.info(f"Pass 1 (caption): generating for picture: {element_id}")
            raw = vlm.generate_response(
                messages=[{"type": "human", "content": VLM_CAPTION_PROMPT}],
                image_input=image_path,
                temperature=0.0,
                max_tokens=VLM_CAPTION_MAX_TOKENS,
            )
            caption = _strip_preamble(_size_guard(raw, VLM_CAPTION_MAX_TOKENS))
        except Exception:
            log.warning(f"Failed to generate caption for picture: {element_id}")
            caption = pic.get("caption", "")

        # --- Pass 2: structured analysis ---
        try:
            log.info(f"Pass 2 (structured): generating for picture: {element_id}")
            raw_struct = vlm.generate_response(
                messages=[{"type": "human", "content": VLM_STRUCTURED_PROMPT}],
                system_prompt=VLM_STRUCTURED_SYSTEM_PROMPT,
                image_input=image_path,
                temperature=VLM_TEMPERATURE,
                max_tokens=VLM_MAX_TOKENS,
            )
            structured = _size_guard(raw_struct, VLM_MAX_TOKENS)
        except Exception:
            log.warning(f"Failed to generate structured analysis for picture: {element_id}")
            structured = ""

        # --- Pass 3: synthesis via LLM ---
        try:
            log.info(f"Pass 3 (synthesis): generating for picture: {element_id}")
            synthesis_prompt = VLM_SYNTHESIS_PROMPT_TEMPLATE.format(
                caption=caption, structured=structured
            )
            raw_synth = llm.generate_response(
                messages=[{"type": "human", "content": synthesis_prompt}],
                system_prompt=VLM_SYNTHESIS_SYSTEM_PROMPT,
                max_tokens=VLM_SYNTHESIS_MAX_TOKENS,
            )
            synthesis = _size_guard(raw_synth, VLM_SYNTHESIS_MAX_TOKENS)
        except Exception:
            log.warning(f"Failed to generate synthesis for picture: {element_id}")
            synthesis = caption

        vision_map[element_id] = {
            "caption": caption,
            "structured": structured,
            "synthesis": synthesis,
        }
        log.info(f"Completed processing picture: {element_id}")

    log.info(f"Completed summarizing all pictures. Processed {len(vision_map)} pictures.")
    return vision_map

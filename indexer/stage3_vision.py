"""Stage 3 — Vision: three-pass picture summarization (caption → structured → synthesis)."""

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
    vision_map: dict[str, dict] = {}

    for pic in pic_info:
        element_id = pic["element_id"]
        image_path = pic.get("image_path")

        if not image_path:
            # No image bytes — fall back to the docling caption if present
            fallback = pic.get("caption", "")
            vision_map[element_id] = {
                "caption": fallback,
                "structured": "",
                "synthesis": fallback,
            }
            continue

        # --- Pass 1: short caption ---
        try:
            raw = vlm.generate_response(
                messages=[{"type": "human", "content": VLM_CAPTION_PROMPT}],
                image_input=image_path,
                temperature=0.0,
                max_tokens=VLM_CAPTION_MAX_TOKENS,
            )
            caption = _strip_preamble(_size_guard(raw, VLM_CAPTION_MAX_TOKENS))
        except Exception:
            caption = pic.get("caption", "")

        # --- Pass 2: structured analysis ---
        try:
            raw_struct = vlm.generate_response(
                messages=[{"type": "human", "content": VLM_STRUCTURED_PROMPT}],
                system_prompt=VLM_STRUCTURED_SYSTEM_PROMPT,
                image_input=image_path,
                temperature=VLM_TEMPERATURE,
                max_tokens=VLM_MAX_TOKENS,
            )
            structured = _size_guard(raw_struct, VLM_MAX_TOKENS)
        except Exception:
            structured = ""

        # --- Pass 3: synthesis via LLM ---
        try:
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
            synthesis = caption

        vision_map[element_id] = {
            "caption": caption,
            "structured": structured,
            "synthesis": synthesis,
        }

    return vision_map

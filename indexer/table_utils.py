from indexer.config import (
    MASSIVE_METRICS_PER_CHUNK,
    MASSIVE_COMPARISON_WINDOW,
    MASSIVE_COMPARISON_OVERLAP,
    MASSIVE_COMPARISON_MAX_METRICS,
)


# ---------------------------------------------------------------------------
# Grid helpers
# ---------------------------------------------------------------------------

def _table_cells_to_grid(table_data: dict) -> list[list[str]]:
    num_rows = table_data.get("num_rows", 0)
    num_cols = table_data.get("num_cols", 0)
    if num_rows == 0 or num_cols == 0:
        return []
    grid: list[list[str]] = [[""] * num_cols for _ in range(num_rows)]
    for cell in table_data.get("table_cells", []):
        r = cell.get("start_row_offset_idx", 0)
        c = cell.get("start_col_offset_idx", 0)
        if r < num_rows and c < num_cols:
            grid[r][c] = str(cell.get("text", "")).strip()
    return grid


def _grid_to_markdown(grid: list[list[str]]) -> str:
    if not grid:
        return ""
    lines = []
    for i, row in enumerate(grid):
        lines.append("| " + " | ".join(row) + " |")
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Massive-table model
# ---------------------------------------------------------------------------

def _is_massive_table_model(table_data: dict) -> bool:
    """
    Guard that decides whether the massive (entity-comparison) strategy applies.
    A table qualifies when it has >= 3 entity columns and >= 6 data rows.
    The first column is treated as the row-label/metric column.
    """
    num_rows = table_data.get("num_rows", 0)
    num_cols = table_data.get("num_cols", 0)
    entity_cols = num_cols - 1  # subtract the metric/label column
    # Determine header row count (assume 1 if any column_header cell exists in row 0)
    has_header = any(
        cell.get("column_header", False) and cell.get("start_row_offset_idx", 0) == 0
        for cell in table_data.get("table_cells", [])
    )
    header_rows = 1 if has_header else 0
    data_rows = num_rows - header_rows
    return entity_cols >= 3 and data_rows >= 6


def _serialize_massive_table_chunks(
    table: dict,
    doc_stem: str,
    metrics_per_chunk: int = MASSIVE_METRICS_PER_CHUNK,
    comparison_window: int = MASSIVE_COMPARISON_WINDOW,
    comparison_overlap: int = MASSIVE_COMPARISON_OVERLAP,
    max_metrics: int = MASSIVE_COMPARISON_MAX_METRICS,
) -> list[dict]:
    """
    Decompose a qualifying comparison/spec table into focused sub-chunks.
    Returns [] for non-qualifying tables; caller falls through to FAQ/spec/general path.
    """
    table_data = table.get("table_data", {})
    if not _is_massive_table_model(table_data):
        return []

    grid = _table_cells_to_grid(table_data)
    if len(grid) < 2:
        return []

    header_row = grid[0]
    data_rows = grid[1:]
    entity_col_indices = list(range(1, len(header_row)))  # skip col-0 (metric labels)

    chunks: list[dict] = []
    col_step = max(1, comparison_window - comparison_overlap)

    for col_start in range(0, len(entity_col_indices), col_step):
        col_window = entity_col_indices[col_start : col_start + comparison_window]
        if not col_window:
            break
        entities = [header_row[c] for c in col_window]

        for row_start in range(0, len(data_rows), metrics_per_chunk):
            row_batch = data_rows[row_start : row_start + min(metrics_per_chunk, max_metrics)]
            if not row_batch:
                break
            metrics = [row[0] for row in row_batch if row]

            sub_header = [header_row[0]] + entities
            sub_rows = [
                [row[0]] + [row[c] if c < len(row) else "" for c in col_window]
                for row in row_batch
            ]
            md = _grid_to_markdown([sub_header] + sub_rows)

            embed_text = (
                f"Comparison table from {doc_stem}.\n"
                f"Entities: {', '.join(entities)}\n"
                f"Metrics: {', '.join(metrics[:5])}{'…' if len(metrics) > 5 else ''}\n\n"
                f"{md}"
            )
            chunks.append({
                "chunk_type": "table_massive",
                "chunk_text_raw": md,
                "chunk_text_embedded": embed_text,
                "rows": len(sub_rows),
                "cols": len(sub_header),
                "table_type": "comparison",
                "page": table.get("page", 0),
                "section": table.get("section", ""),
            })

    return chunks


# ---------------------------------------------------------------------------
# General table helpers
# ---------------------------------------------------------------------------

def _table_to_markdown(table: dict) -> str:
    return _grid_to_markdown(_table_cells_to_grid(table.get("table_data", {})))


def _detect_table_type(table: dict) -> str:
    """Classify table as 'faq', 'spec', or 'general'."""
    table_data = table.get("table_data", {})
    if _is_massive_table_model(table_data):
        return "spec"

    grid = _table_cells_to_grid(table_data)
    if len(grid) >= 2 and table_data.get("num_cols", 0) == 2:
        first_col_text = " ".join(row[0] for row in grid[1:] if row).lower()
        if any(kw in first_col_text for kw in ["what", "how", "why", "when", "where", "who", "?"]):
            return "faq"

    return "general"

import io
import zipfile

import pytest

from core.mineru import MinerUResult
from indexer import stage1_parse


class DoclingSuccess:
    def convert_file_with_polling(self, path, to_formats):
        return {"document": {"json_content": {
            "texts": [{"self_ref": "#/texts/0", "label": "text", "text": "Docling text", "prov": [{"page_no": 1}]}],
            "body": {"children": [{"$ref": "#/texts/0"}]},
        }}}


class DoclingFailure:
    def convert_file_with_polling(self, path, to_formats):
        raise RuntimeError("unavailable")


class MinerUSuccess:
    enabled = True

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def parse_pdf(self, path):
        self.calls += 1
        return self.result


def test_pdf_docling_success_does_not_call_mineru(tmp_path):
    mineru = MinerUSuccess(MinerUResult({"pages": []}, None, None))

    elements, _ = stage1_parse.parse(str(tmp_path / "document.pdf"), str(tmp_path), DoclingSuccess(), mineru)

    assert elements[0]["text"] == "Docling text"
    assert mineru.calls == 0


def test_pdf_docling_failure_uses_mineru_structured_content(tmp_path):
    result = MinerUResult({"pages": [{"blocks": [{"type": "text", "text": "MinerU text"}]}]}, None, None)
    mineru = MinerUSuccess(result)

    elements, _ = stage1_parse.parse(str(tmp_path / "document.pdf"), str(tmp_path), DoclingFailure(), mineru)

    assert elements == [{"type": "text", "text": "MinerU text", "page": 1, "section": ""}]
    assert mineru.calls == 1


def test_pdf_docling_empty_output_uses_mineru(tmp_path):
    mineru = MinerUSuccess(MinerUResult({"pages": [{"blocks": [{"type": "text", "text": "fallback"}]}]}, None, None))

    elements, _ = stage1_parse.parse(str(tmp_path / "document.pdf"), str(tmp_path), DoclingSuccessEmpty(), mineru)

    assert elements[0]["text"] == "fallback"
    assert mineru.calls == 1


class DoclingSuccessEmpty:
    def convert_file_with_polling(self, path, to_formats):
        return {"document": {"json_content": {"texts": [], "body": {"children": []}}}}


def test_both_pdf_parsers_failing_raise_single_parser_error(tmp_path):
    mineru = MinerUSuccess(MinerUResult({"pages": []}, None, None))

    with pytest.raises(stage1_parse.ParserError, match="Docling .* MinerU"):
        stage1_parse.parse(str(tmp_path / "document.pdf"), str(tmp_path), DoclingFailure(), mineru)


def test_non_pdf_docling_failure_does_not_call_mineru(tmp_path):
    mineru = MinerUSuccess(MinerUResult({"pages": []}, None, None))

    with pytest.raises(RuntimeError, match="unavailable"):
        stage1_parse.parse(str(tmp_path / "document.docx"), str(tmp_path), DoclingFailure(), mineru)

    assert mineru.calls == 0


def test_normalizes_headings_tables_images_and_zero_based_pages(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("images/chart.png", b"image-data")
    result = MinerUResult({"pages": [{"blocks": [
        {"type": "heading", "text": "Overview"},
        {"type": "table", "rows": [["A", "B"], ["1", "2"]]},
        {"type": "image", "image_path": "images/chart.png", "caption": "Chart"},
    ]}]}, None, archive.getvalue())

    elements, pictures = stage1_parse._parse_mineru_result(result, str(tmp_path))

    assert [element["type"] for element in elements] == ["heading", "table", "picture"]
    assert all(element["page"] == 1 for element in elements)
    assert elements[1]["table_data"]["num_rows"] == 2
    assert pictures[0]["page"] == 1
    assert pictures[0]["caption"] == "Chart"
    assert (tmp_path / "mineru_chart.png").read_bytes() == b"image-data"

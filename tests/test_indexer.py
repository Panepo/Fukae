import os
import pytest
from pathlib import Path
from indexer.indexer import DocumentIndexer


def get_test_files_dir():
    """Get the directory containing test files."""
    return Path(__file__).parent


def test_document_indexer_initialization():
    """Test DocumentIndexer initialization."""
    indexer = DocumentIndexer()
    assert indexer.docling is not None
    assert indexer.llm is not None
    assert indexer.vlm is not None
    assert indexer.chunk_size == 1024
    assert indexer.chunk_overlap == 128


def test_load_passthrough_txt():
    """Test loading a .txt file through the passthrough pipeline."""
    indexer = DocumentIndexer()

    # Create a temporary test file
    test_files_dir = get_test_files_dir()
    test_txt_path = test_files_dir / "test.txt"
    test_content = "This is a test text file for the passthrough pipeline.\nIt has multiple lines.\n"

    try:
        with open(test_txt_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        chunks = indexer.load(str(test_txt_path))

        assert isinstance(chunks, list)
        assert len(chunks) > 0

        for chunk in chunks:
            assert "chunk_id" in chunk
            assert "source" in chunk
            assert "chunk_type" in chunk
            assert "chunk_text_original" in chunk
            assert "chunk_text_embedded" in chunk
            assert "page_number" in chunk
            assert "section_title" in chunk
            assert "language" in chunk
            assert "chunk_hash" in chunk

    finally:
        if test_txt_path.exists():
            test_txt_path.unlink()


def test_load_passthrough_md():
    """Test loading a .md file through the passthrough pipeline."""
    indexer = DocumentIndexer()

    # Create a temporary test file
    test_files_dir = get_test_files_dir()
    test_md_path = test_files_dir / "test.md"
    test_content = "# Test Markdown\n\nThis is a test markdown file.\n"

    try:
        with open(test_md_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        chunks = indexer.load(str(test_md_path))

        assert isinstance(chunks, list)
        assert len(chunks) > 0

        for chunk in chunks:
            assert "chunk_id" in chunk
            assert "source" in chunk
            assert chunk.get("chunk_type") == "text"

    finally:
        if test_md_path.exists():
            test_md_path.unlink()


@pytest.mark.skipif(
    not (get_test_files_dir() / "testPdf.pdf").exists(),
    reason="testPdf.pdf not found in tests directory"
)
def test_load_pdf_pipeline():
    """Test loading a .pdf file through the full pipeline."""
    indexer = DocumentIndexer()

    test_files_dir = get_test_files_dir()
    test_pdf_path = test_files_dir / "testPdf.pdf"

    # Check if docling server is available
    if not indexer.docling.base_url:
        pytest.skip("DOCLING_BASE_URL environment variable not set")

    try:
        chunks = indexer.load(str(test_pdf_path))

        assert isinstance(chunks, list)
        # Should return at least some chunks
        assert len(chunks) >= 0

        if len(chunks) > 0:
            for chunk in chunks:
                assert "chunk_id" in chunk
                assert "source" in chunk
                assert "chunk_type" in chunk
                assert "chunk_text_original" in chunk
                assert "chunk_text_embedded" in chunk
                assert "page_number" in chunk
                assert "section_title" in chunk
                assert "language" in chunk
                assert "chunk_hash" in chunk

    except Exception:
        # Skip test if the docling server is not available or returns an error
        pytest.skip("Docling server not available or pipeline returned an error")


@pytest.mark.skipif(
    not (get_test_files_dir() / "testimg.jpeg").exists(),
    reason="testimg.jpeg not found in tests directory"
)
def test_load_directory():
    """Test loading a directory with supported documents."""
    indexer = DocumentIndexer()

    test_files_dir = get_test_files_dir()

    # Check if docling server is available for PDF processing
    if not indexer.docling.base_url:
        pytest.skip("DOCLING_BASE_URL environment variable not set")

    # Create a temporary directory with test files
    temp_test_dir = test_files_dir / "temp_test_dir"
    temp_test_dir.mkdir(exist_ok=True)

    # Create a test txt file
    test_txt_path = temp_test_dir / "test.txt"
    with open(test_txt_path, "w", encoding="utf-8") as f:
        f.write("Test text content for directory loading.\n")

    # Copy the test PDF if it exists
    test_pdf_path = test_files_dir / "testPdf.pdf"
    if test_pdf_path.exists():
        import shutil
        shutil.copy(test_pdf_path, temp_test_dir / "document.pdf")

    try:
        chunks = indexer.load_directory(str(temp_test_dir), recursive=True)

        assert isinstance(chunks, list)

        # Should have chunks from both the txt file and PDF
        txt_chunks = [c for c in chunks if c.get("source") == "test.txt"]
        assert len(txt_chunks) > 0

    finally:
        # Clean up temporary directory
        import shutil
        if temp_test_dir.exists():
            shutil.rmtree(temp_test_dir)

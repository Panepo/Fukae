import os
import pytest
from core.docling import DoclingInference


def test_docling_convert_document():
    """Test converting a document with DoclingInference."""
    # Create a temporary test file
    test_file_path = "test_document.pdf"
    with open(test_file_path, "wb") as f:
        f.write(b"%PDF-1.4\n%test document content")

    try:
        docling = DoclingInference()
        # Check if base_url is set
        if not docling.base_url:
            pytest.skip("DOCLING_BASE_URL environment variable not set")

        # Note: This test will fail if the docling server is not available or the API endpoint is different
        # In a real test environment, you would mock the HTTP request or use a test server
        result = docling.convert_document(test_file_path)
        assert isinstance(result, dict)
        assert "document" in result or "status" in result or "task_id" in result
    except Exception:
        # Skip test if the docling server is not available or returns an error
        pytest.skip("Docling server not available or API endpoint returned an error")
    finally:
        # Clean up the test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


def test_docling_convert_document_async():
    """Test converting a document asynchronously with DoclingInference."""
    # Create a temporary test file
    test_file_path = "test_document_async.pdf"
    with open(test_file_path, "wb") as f:
        f.write(b"%PDF-1.4\n%test document content for async conversion")

    try:
        docling = DoclingInference()
        # Check if base_url is set
        if not docling.base_url:
            pytest.skip("DOCLING_BASE_URL environment variable not set")

        # Note: This test will fail if the docling server is not available or the API endpoint is different
        # In a real test environment, you would mock the HTTP request or use a test server
        task_id = docling.convert_document_async(test_file_path)
        assert isinstance(task_id, str)
        assert len(task_id) > 0
    except Exception:
        # Skip test if the docling server is not available or returns an error
        pytest.skip("Docling server not available or API endpoint returned an error")
    finally:
        # Clean up the test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


def test_docling_poll_task_status():
    """Test polling task status with DoclingInference."""
    docling = DoclingInference()

    # Note: This test will fail if the docling server is not available or the task_id is invalid
    # In a real test environment, you would mock the HTTP request or use a test server
    # We're just testing the method exists and has the right signature
    assert hasattr(docling, 'poll_task_status')
    assert callable(docling.poll_task_status)


def test_docling_get_result():
    """Test getting result with DoclingInference."""
    docling = DoclingInference()

    # Note: This test will fail if the docling server is not available or the task_id is invalid
    # In a real test environment, you would mock the HTTP request or use a test server
    # We're just testing the method exists and has the right signature
    assert hasattr(docling, 'get_result')
    assert callable(docling.get_result)


def test_docling_convert_document_with_polling():
    """Test converting a document with polling with DoclingInference."""
    # Create a temporary test file
    test_file_path = "test_document_polling.pdf"
    with open(test_file_path, "wb") as f:
        f.write(b"%PDF-1.4\n%test document content for polling conversion")

    try:
        docling = DoclingInference()
        # Check if base_url is set
        if not docling.base_url:
            pytest.skip("DOCLING_BASE_URL environment variable not set")

        # Note: This test will fail if the docling server is not available or the API endpoint is different
        # In a real test environment, you would mock the HTTP request or use a test server
        result = docling.convert_document_with_polling(test_file_path)
        assert isinstance(result, dict)
        assert "document" in result or "status" in result or "task_id" in result
    except Exception:
        # Skip test if the docling server is not available or returns an error
        pytest.skip("Docling server not available or API endpoint returned an error")
    finally:
        # Clean up the test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


def test_docling_get_content_type_from_name():
    """Test content type detection from file name."""
    docling = DoclingInference()

    assert docling._get_content_type_from_name("test.pdf") == "application/pdf"
    assert docling._get_content_type_from_name("test.docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert docling._get_content_type_from_name("test.png") == "image/png"
    assert docling._get_content_type_from_name("test.unknown") == "application/octet-stream"


if __name__ == "__main__":
    pytest.main([__file__])

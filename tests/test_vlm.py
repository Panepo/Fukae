import os
import pytest
from core.vlm import VLMInference
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


def test_vlm_initialization():
    """Test VLM initialization with environment variables."""
    vlm = VLMInference()
    assert vlm.model_name is not None or vlm.model_name == ""
    assert vlm.base_url is not None or vlm.base_url == ""
    assert vlm.api_key is not None or vlm.api_key == ""


def test_generate_response_with_system_prompt():
    """Test generating a response with a system prompt."""
    vlm = VLMInference()

    # Skip test if environment variables are not set
    if not vlm.model_name or not vlm.base_url or not vlm.api_key:
        pytest.skip("VLM environment variables not set")

    system_prompt = "You are a helpful assistant that provides concise answers."
    messages = [
        {"type": "human", "content": "What is the capital of France?"}
    ]

    response = vlm.generate_response(messages=messages, system_prompt=system_prompt)

    assert isinstance(response, str)
    assert len(response) > 0
    # Check if the response mentions Paris (capital of France)
    assert "paris" in response.lower() or "france" in response.lower()


def test_generate_response_with_message_list():
    """Test generating a response with a list of messages."""
    vlm = VLMInference()

    # Skip test if environment variables are not set
    if not vlm.model_name or not vlm.base_url or not vlm.api_key:
        pytest.skip("VLM environment variables not set")

    messages = [
        {"type": "system", "content": "You are a helpful assistant."},
        {"type": "human", "content": "What is 2+2?"},
        {"type": "ai", "content": "2+2 is 4."},
        {"type": "human", "content": "What is 3+3?"}
    ]

    response = vlm.generate_response(messages=messages)

    assert isinstance(response, str)
    assert len(response) > 0
    # Check if the response mentions 6
    assert "6" in response or "six" in response.lower()


def test_generate_response_with_langchain_messages():
    """Test generating a response with LangChain message objects."""
    vlm = VLMInference()

    # Skip test if environment variables are not set
    if not vlm.model_name or not vlm.base_url or not vlm.api_key:
        pytest.skip("VLM environment variables not set")

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="What is the largest planet in our solar system?")
    ]

    response = vlm.generate_response(messages=messages)

    assert isinstance(response, str)
    assert len(response) > 0
    # Check if the response mentions Jupiter
    assert "jupiter" in response.lower()


def test_stream_response():
    """Test streaming responses from the VLM."""
    vlm = VLMInference()

    # Skip test if environment variables are not set
    if not vlm.model_name or not vlm.base_url or not vlm.api_key:
        pytest.skip("VLM environment variables not set")

    system_prompt = "You are a helpful assistant that provides concise answers."
    messages = [
        {"type": "human", "content": "What is the capital of Germany?"}
    ]

    # Collect all streamed chunks
    streamed_response = ""
    for chunk in vlm.stream_response(messages=messages, system_prompt=system_prompt):
        streamed_response += chunk

    assert isinstance(streamed_response, str)
    assert len(streamed_response) > 0
    # Check if the response mentions Berlin (capital of Germany)
    assert "berlin" in streamed_response.lower() or "germany" in streamed_response.lower()


def test_generate_response_with_image_input():
    """Test generating a response with an image input."""
    vlm = VLMInference()

    # Skip test if environment variables are not set
    if not vlm.model_name or not vlm.base_url or not vlm.api_key:
        pytest.skip("VLM environment variables not set")

    # Use a sample image file for testing
    sample_image_path = "./tests/testimg.jpeg"

    messages = [
        {"type": "human", "content": "Describe this image."}
    ]

    response = vlm.generate_response(messages=messages, image_input=sample_image_path)

    assert isinstance(response, str)
    assert len(response) > 0

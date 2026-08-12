import os
import pytest
from core.llm import LLMInference
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

def test_llm_initialization():
    """Test LLM initialization with environment variables."""
    llm = LLMInference()
    assert llm.model_name is not None or llm.model_name == ""
    assert llm.base_url is not None or llm.base_url == ""
    assert llm.api_key is not None or llm.api_key == ""

def test_generate_response_with_system_prompt():
    """Test generating a response with a system prompt."""
    llm = LLMInference()

    # Skip test if environment variables are not set
    if not llm.model_name or not llm.base_url or not llm.api_key:
        pytest.skip("LLM environment variables not set")

    system_prompt = "You are a helpful assistant that provides concise answers."
    messages = [
        {"type": "human", "content": "What is the capital of France?"}
    ]

    response = llm.generate_response(messages=messages, system_prompt=system_prompt)

    assert isinstance(response, str)
    assert len(response) > 0
    # Check if the response mentions Paris (capital of France)
    assert "paris" in response.lower() or "france" in response.lower()

def test_generate_response_with_message_list():
    """Test generating a response with a list of messages."""
    llm = LLMInference()

    # Skip test if environment variables are not set
    if not llm.model_name or not llm.base_url or not llm.api_key:
        pytest.skip("LLM environment variables not set")

    messages = [
        {"type": "system", "content": "You are a helpful assistant."},
        {"type": "human", "content": "What is 2+2?"},
        {"type": "ai", "content": "2+2 is 4."},
        {"type": "human", "content": "What is 3+3?"}
    ]

    response = llm.generate_response(messages=messages)

    assert isinstance(response, str)
    assert len(response) > 0
    # Check if the response mentions 6
    assert "6" in response or "six" in response.lower()

def test_generate_response_with_langchain_messages():
    """Test generating a response with LangChain message objects."""
    llm = LLMInference()

    # Skip test if environment variables are not set
    if not llm.model_name or not llm.base_url or not llm.api_key:
        pytest.skip("LLM environment variables not set")

    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="What is the largest planet in our solar system?")
    ]

    response = llm.generate_response(messages=messages)

    assert isinstance(response, str)
    assert len(response) > 0
    # Check if the response mentions Jupiter
    assert "jupiter" in response.lower()

def test_stream_response():
    """Test streaming responses from the LLM."""
    llm = LLMInference()

    # Skip test if environment variables are not set
    if not llm.model_name or not llm.base_url or not llm.api_key:
        pytest.skip("LLM environment variables not set")

    system_prompt = "You are a helpful assistant that provides concise answers."
    messages = [
        {"type": "human", "content": "What is the capital of Germany?"}
    ]

    # Collect all streamed chunks
    streamed_response = ""
    for chunk in llm.stream_response(messages=messages, system_prompt=system_prompt):
        streamed_response += chunk

    assert isinstance(streamed_response, str)
    assert len(streamed_response) > 0
    # Check if the response mentions Berlin (capital of Germany)
    assert "berlin" in streamed_response.lower() or "germany" in streamed_response.lower()

def test_create_prompt_template():
    """Test creating a chat prompt template."""
    llm = LLMInference()

    template = "Translate the following text to French: {text}"
    prompt_template = llm.create_prompt_template(template)

    assert prompt_template is not None
    # Check if the template has the expected structure
    assert hasattr(prompt_template, 'format')

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

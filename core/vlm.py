import os
import base64
import mimetypes
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Load environment variables
load_dotenv()


class VLMInference:
    def __init__(self, temperature: float = 0.7):
        """Initialize the VLM inference class with vision chat model configuration."""
        self.model_name = os.getenv("VISION_CHAT_MODEL", "")
        self.base_url = os.getenv("VISION_CHAT_BASE_URL", "")
        self.api_key = os.getenv("VISION_CHAT_API_KEY", "")
        self.temperature = temperature

        # Initialize the ChatOpenAI client for vision models
        self.vlm = ChatOpenAI(
            model=self.model_name,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature
        )

    def generate_response(self, messages: list = None, system_prompt: str = None, image_input: str = None, temperature: float = None) -> str:
        """
        Generate a response from the VLM based on the given messages or prompt.

        Args:
            messages (list, optional): List of messages including chat history and tool messages
            system_prompt (str, optional): System prompt to set context
            image_input (str, optional): Image input (URL or base64 encoded image)
            temperature (float, optional): Temperature for the VLM response

        Returns:
            str: The generated response
        """
        message_list = []

        if system_prompt:
            message_list.append(SystemMessage(content=system_prompt))

        # Prepare human message content
        human_content_parts = []

        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    # Handle dictionary format messages
                    msg_type = msg.get('type', 'human')
                    content = msg.get('content', '')

                    if msg_type == 'system':
                        message_list.append(SystemMessage(content=content))
                    elif msg_type == 'human':
                        # Add text content to human_content_parts
                        if isinstance(content, list):
                            human_content_parts.extend(content)
                        else:
                            human_content_parts.append({"type": "text", "text": content})
                    elif msg_type == 'ai':
                        message_list.append(AIMessage(content=content))
                    elif msg_type == 'tool':
                        from langchain_core.messages import ToolMessage
                        tool_call_id = msg.get('tool_call_id')
                        message_list.append(ToolMessage(content=content, tool_call_id=tool_call_id))
                elif hasattr(msg, 'content'):
                    # Handle LangChain message objects
                    if isinstance(msg, HumanMessage):
                        if isinstance(msg.content, list):
                            human_content_parts.extend(msg.content)
                        else:
                            human_content_parts.append({"type": "text", "text": str(msg.content)})
                    else:
                        message_list.append(msg)
        else:
            # Fallback to single prompt if no messages provided
            human_content_parts.append({"type": "text", "text": ""})

        # Add image input if provided
        if image_input:
            if os.path.isfile(image_input):
                mime_type, _ = mimetypes.guess_type(image_input)
                mime_type = mime_type or "image/jpeg"
                with open(image_input, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                image_url = f"data:{mime_type};base64,{b64}"
            else:
                image_url = image_input
            human_content_parts.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        # Create the human message with text and image content
        if human_content_parts:
            message_list.append(HumanMessage(content=human_content_parts))

        # Use the provided temperature or fall back to the instance temperature
        effective_temperature = temperature if temperature is not None else self.temperature

        # Bind the temperature to the VLM and invoke
        vlm_with_temperature = self.vlm.bind(temperature=effective_temperature)
        response = vlm_with_temperature.invoke(message_list)

        return response.content

    def stream_response(self, messages: list = None, system_prompt: str = None, image_input: str = None, temperature: float = None):
        """
        Stream responses from the VLM.

        Args:
            messages (list, optional): List of messages including chat history and tool messages
            system_prompt (str, optional): System prompt to set context
            image_input (str, optional): Image input (URL or base64 encoded image)
            temperature (float, optional): Temperature for the VLM response

        Yields:
            str: Chunks of the generated response
        """
        message_list = []

        if system_prompt:
            message_list.append(SystemMessage(content=system_prompt))

        # Prepare human message content
        human_content_parts = []

        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    # Handle dictionary format messages
                    msg_type = msg.get('type', 'human')
                    content = msg.get('content', '')

                    if msg_type == 'system':
                        message_list.append(SystemMessage(content=content))
                    elif msg_type == 'human':
                        # Add text content to human_content_parts
                        if isinstance(content, list):
                            human_content_parts.extend(content)
                        else:
                            human_content_parts.append({"type": "text", "text": content})
                    elif msg_type == 'ai':
                        message_list.append(AIMessage(content=content))
                    elif msg_type == 'tool':
                        from langchain_core.messages import ToolMessage
                        tool_call_id = msg.get('tool_call_id')
                        message_list.append(ToolMessage(content=content, tool_call_id=tool_call_id))
                elif hasattr(msg, 'content'):
                    # Handle LangChain message objects
                    if isinstance(msg, HumanMessage):
                        if isinstance(msg.content, list):
                            human_content_parts.extend(msg.content)
                        else:
                            human_content_parts.append({"type": "text", "text": str(msg.content)})
                    else:
                        message_list.append(msg)
        else:
            # Fallback to single prompt if no messages provided
            human_content_parts.append({"type": "text", "text": ""})

        # Add image input if provided
        if image_input:
            if os.path.isfile(image_input):
                mime_type, _ = mimetypes.guess_type(image_input)
                mime_type = mime_type or "image/jpeg"
                with open(image_input, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                image_url = f"data:{mime_type};base64,{b64}"
            else:
                image_url = image_input
            human_content_parts.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        # Create the human message with text and image content
        if human_content_parts:
            message_list.append(HumanMessage(content=human_content_parts))

        # Use the provided temperature or fall back to the instance temperature
        effective_temperature = temperature if temperature is not None else self.temperature

        # Bind the temperature to the VLM and stream
        vlm_with_temperature = self.vlm.bind(temperature=effective_temperature)

        # Stream the VLM response
        for chunk in vlm_with_temperature.stream(message_list):
            if hasattr(chunk, 'content') and chunk.content is not None:
                yield chunk.content

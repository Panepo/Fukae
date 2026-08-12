import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables
load_dotenv()

class LLMInference:
    def __init__(self, temperature: float = 0.7):
        """Initialize the LLM inference class with chat model configuration."""
        self.model_name = os.getenv("CHAT_MODEL", "")
        self.base_url = os.getenv("CHAT_BASE_URL", "")
        self.api_key = os.getenv("CHAT_API_KEY", "")
        self.temperature = temperature

        # Initialize the ChatOpenAI client
        self.llm = ChatOpenAI(
            model=self.model_name,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature
        )

    def generate_response(self, messages: list = None, system_prompt: str = None, temperature: float = None) -> str:
        """
        Generate a response from the LLM based on the given messages or prompt.

        Args:
            messages (list, optional): List of messages including chat history and tool messages
            system_prompt (str, optional): System prompt to set context
            temperature (float, optional): Temperature for the LLM response

        Returns:
            str: The generated response
        """
        message_list = []

        if system_prompt:
            message_list.append(SystemMessage(content=system_prompt))

        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    # Handle dictionary format messages
                    msg_type = msg.get('type', 'human')
                    content = msg.get('content', '')

                    if msg_type == 'system':
                        message_list.append(SystemMessage(content=content))
                    elif msg_type == 'human':
                        message_list.append(HumanMessage(content=content))
                    elif msg_type == 'ai':
                        from langchain_core.messages import AIMessage
                        message_list.append(AIMessage(content=content))
                    elif msg_type == 'tool':
                        from langchain_core.messages import ToolMessage
                        tool_call_id = msg.get('tool_call_id')
                        message_list.append(ToolMessage(content=content, tool_call_id=tool_call_id))
                elif hasattr(msg, 'content'):
                    # Handle LangChain message objects
                    message_list.append(msg)
        else:
            # Fallback to single prompt if no messages provided
            message_list.append(HumanMessage(content=""))

        # Use the provided temperature or fall back to the instance temperature
        effective_temperature = temperature if temperature is not None else self.temperature

        # Bind the temperature to the LLM and invoke
        llm_with_temperature = self.llm.bind(temperature=effective_temperature)
        response = llm_with_temperature.invoke(message_list)

        return response.content

    def create_prompt_template(self, template: str) -> ChatPromptTemplate:
        """
        Create a chat prompt template.

        Args:
            template (str): The prompt template string

        Returns:
            ChatPromptTemplate: The created prompt template
        """
        return ChatPromptTemplate.from_template(template)

    def stream_response(self, messages: list = None, system_prompt: str = None, temperature: float = None):
        """
        Stream responses from the LLM.

        Args:
            messages (list, optional): List of messages including chat history and tool messages
            system_prompt (str, optional): System prompt to set context
            temperature (float, optional): Temperature for the LLM response

        Yields:
            str: Chunks of the generated response
        """
        message_list = []

        if system_prompt:
            message_list.append(SystemMessage(content=system_prompt))

        if messages:
            for msg in messages:
                if isinstance(msg, dict):
                    # Handle dictionary format messages
                    msg_type = msg.get('type', 'human')
                    content = msg.get('content', '')

                    if msg_type == 'system':
                        message_list.append(SystemMessage(content=content))
                    elif msg_type == 'human':
                        message_list.append(HumanMessage(content=content))
                    elif msg_type == 'ai':
                        from langchain_core.messages import AIMessage
                        message_list.append(AIMessage(content=content))
                    elif msg_type == 'tool':
                        from langchain_core.messages import ToolMessage
                        tool_call_id = msg.get('tool_call_id')
                        message_list.append(ToolMessage(content=content, tool_call_id=tool_call_id))
                elif hasattr(msg, 'content'):
                    # Handle LangChain message objects
                    message_list.append(msg)
        else:
            # Fallback to single prompt if no messages provided
            message_list.append(HumanMessage(content=""))

        # Use the provided temperature or fall back to the instance temperature
        effective_temperature = temperature if temperature is not None else self.temperature

        # Bind the temperature to the LLM and stream
        llm_with_temperature = self.llm.bind(temperature=effective_temperature)

        # Stream the LLM response
        for chunk in llm_with_temperature.stream(message_list):
            if hasattr(chunk, 'content') and chunk.content is not None:
                yield chunk.content

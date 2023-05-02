import os
from typing import Optional, List

import openai

# TODO this is an attempt to make the adapter more idiomatic, it's not being used

class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self):
        return {"role": self.role, "content": self.content}


class Conversation:
    def __init__(self, initial_system_message: str = "You are a helpful assistant."):
        self.messages = [Message("system", initial_system_message)]

    def add_user_message(self, content: str):
        self.messages.append(Message("user", content))

    def add_assistant_message(self, content: str):
        self.messages.append(Message("assistant", content))

    def to_dict_list(self):
        return [msg.to_dict() for msg in self.messages]


class OpenAIAdapter:
    def __init__(self, api_key=os.getenv("OPEN_AI_API_KEY"), model: Optional[str] = None):
        openai.api_key = api_key
        self.model = model or "gpt-3.5-turbo"

    def _send_message(self, message_log, model: Optional[str] = None) -> str:
        if model is None:
            model = self.model
        response = openai.ChatCompletion.create(
            model=model,
            messages=message_log,
            temperature=0.7,
        )

        for choice in response.choices:
            if "text" in choice:
                return choice.text

        return response.choices[0].message.content

    def process_message(self, conversation: Conversation, message: str, model: Optional[str] = None) -> None:
        if message.lower() == "quit":
            conversation.messages = []
            return
        if message[:6] == "/clean":
            conversation.messages = []
            message = message[6:]
        conversation.add_user_message(message)

        response = self._send_message(conversation.to_dict_list(), model=model)
        conversation.add_assistant_message(response)

    def answer_message(self, conversation: Conversation, message: str, model: Optional[str] = None) -> str:
        self.process_message(conversation, message, model=model)
        return f"{conversation.messages[-1].content} \nmessage #{len(conversation.messages)}"


if __name__ == '__main__':
    my_openai = OpenAIAdapter()

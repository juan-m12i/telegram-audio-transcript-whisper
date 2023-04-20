import os
from typing import Optional, List

import openai


# TODO refactor the methods of this class into something more idiomatic, it should be cleaner
class OpenAI:
    def __init__(self, api_key=os.getenv("OPEN_AI_API_KEY"), model: Optional[str] = None):
        # Set up OpenAI API key
        openai.api_key = api_key
        self.messages: Optional[List[dict]] = None
        self.model = model or "gpt-3.5-turbo"

    # Function to send a message to the OpenAI chatbot model and return its response
    def send_message(self, message_log, model: Optional[str] = None) -> str:
        # Use OpenAI's ChatCompletion API to get the chatbot's response
        if model is None:
            model = self.model
        response = openai.ChatCompletion.create(
            model=model,  # The name of the OpenAI chatbot model to use
            messages=message_log,   # The conversation history up to this point, as a list of dictionaries
            # max_tokens=4096,        # The maximum number of tokens (words or subwords) in the generated response
            stop=None,              # The stopping sequence for the generated response, if any (not used here)
            temperature=0.7,        # The "creativity" of the generated response (higher temperature = more creative)
        )

        # Find the first response from the chatbot that has text in it (some responses may not have text)
        for choice in response.choices:
            if "text" in choice:
                return choice.text

        # If no response with text is found, return the first response's content (which may be empty)
        return response.choices[0].message.content

    def process_message(self, message, model: Optional[str] = None) -> None:
        # Set a flag to keep track of whether this is the first request in the conversation
        if message.lower() == "quit":
            self.messages = None
            return
        if message[:6] == "/clean":
            self.messages = None
            message = message[6:]
        if self.messages is None:
            self.messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": message},
            ]
        else:
            self.messages.append(
                {"role": "user", "content": message},
            )

        response = self.send_message(self.messages, model=model)
        self.messages.append({"role": "assistant", "content": response})

    def answer_message(self, message, model: Optional[str] = None) -> str:
        self.process_message(message, model=model)
        return f"{self.messages[-1].get('content')} - message #{len(self.messages)}"


if __name__ == '__main__':
    my_openai = OpenAI()

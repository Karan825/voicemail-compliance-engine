import os
from groq import Groq
from dotenv import load_dotenv
from groq.types.chat import ChatCompletionUserMessageParam

load_dotenv()

class GreetingLLM:
    def __init__(self):
        self.client = Groq()

    def greeting_finished(self, transcript):
        if len(transcript) < 20:
            return False

        prompt = f"""
You are classifying voicemail greetings.

Transcript:
"{transcript}"

Question:
Has the voicemail greeting finished, such that recording can safely start?

Answer ONLY with YES or NO.
"""

        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                ChatCompletionUserMessageParam(
                    role="user",
                    content=prompt
                )
            ]
            ,
            temperature=0,
            max_tokens=5
        )

        answer = response.choices[0].message.content.strip()

        print("LLM raw output:", repr(answer))  # debug

        return answer.upper().startswith("YES")


llm = GreetingLLM()

print(
    llm.greeting_finished(
        "hi you've reached mike rodriguez i can't take your call right now please leave a message after the beep"
    )
)

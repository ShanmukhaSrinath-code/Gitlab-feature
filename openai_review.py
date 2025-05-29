# openai_review.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()  # reads OPENAI_API_KEY from env automatically

async def generate_code_review(diff: str) -> str:
    system_prompt = "You are a senior software engineer performing code review. Provide feedback on the following code changes."

    prompt = f"Here is the code diff:\n\n{diff}\n\nPlease review it and suggest improvements."

    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # or "gpt-4"
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=500,
        temperature=0.4,
    )

    review_comments = response.choices[0].message.content.strip()
    return review_comments

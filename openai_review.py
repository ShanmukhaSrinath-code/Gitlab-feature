import os
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")


async def generate_code_review(diff: str) -> str:
    system_prompt = "You are a senior software engineer performing code review. Provide feedback on the following code changes."

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is the code diff:\n\n{diff}\n\nPlease review it and suggest improvements."}
        ],
        max_tokens=500,
        temperature=0.4
    )

    review_comments = response.choices[0].message.content.strip()
    return review_comments

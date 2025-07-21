import os
import openai
from openai import OpenAI
import pandas as pd
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_reviews(prompt, num_rows=10, model="gpt-3.5-turbo"):
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that generates realistic synthetic datasets."
        },
        {
            "role": "user",
            "content": f"{prompt}.\nReturn {num_rows} rows in CSV format without any explanation."
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7
    )

    return response.choices[0].message.content

# Example prompt
if __name__ == "__main__":
    user_prompt = input("Enter your synthetic dataset prompt: ")
    csv_data = generate_reviews(user_prompt, num_rows=10)
    print(csv_data)
    with open("synthetic_reviews.csv", "w", encoding="utf-8") as f:
        f.write(csv_data)

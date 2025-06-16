import os
from openai import OpenAI
import pandas as pd

client = OpenAI(api_key="")  # replace with your actual key


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
user_prompt = input("Enter your synthetic dataset prompt: ")
# prompt = "Generate a dataset of movies with columns: name, year, genre, rating"
csv_data = generate_reviews(user_prompt, num_rows=10)

# Print and save
print(csv_data)
with open("synthetic_reviews.csv", "w", encoding="utf-8") as f:
    f.write(csv_data)

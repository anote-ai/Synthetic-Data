import os
import openai
from openai import OpenAI
import pandas as pd
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_reviews(prompt, num_rows=20, columns=None, model="gpt-3.5-turbo"):
    columns_str = f"The CSV columns should be: {', '.join(columns)}." if columns else ""
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that generates realistic synthetic datasets. You can gather information from the web to generate the dataset. If there is no information available, you can generate a dataset based on your knowledge. The generated dataset can have values which are not real but are plausible."
        },
        {
            "role": "user",
            "content": f"{prompt}. {columns_str} Return exactly {num_rows} rows in CSV format. Do not return more or less than {num_rows} rows. Do not include any explanation."
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
    num_rows = int(input("Enter the number of rows to generate: "))
    columns_input = input("Enter the column names (comma-separated): ")
    columns = [col.strip() for col in columns_input.split(",") if col.strip()]
    csv_data = generate_reviews(user_prompt, num_rows=num_rows, columns=columns)
    print(csv_data)
    with open("synthetic_reviews.csv", "w", encoding="utf-8") as f:
        f.write(csv_data)

'''Generate a dataset of reviews for beauty products from sephora.com'''


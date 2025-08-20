# # def generate_text_data(prompt, columns, num_rows, examples):
# #     results = []
# #     for i in range(num_rows):
# #         row = {col: f"Generated {col} value {i}" for col in columns}
# #         results.append(row)
# #     return results

# import os
# import openai
# from openai import OpenAI
# import pandas as pd
# import json
# from dotenv import load_dotenv
# import os

# # Load environment variables from .env
# load_dotenv()

# # Initialize OpenAI client with error handling
# try:
#     api_key = os.getenv("OPENAI_API_KEY")
#     if api_key and api_key != "your_openai_api_key_here":
#         client = openai.OpenAI(api_key=api_key)
#         OPENAI_AVAILABLE = True
#         print(f"OpenAI client initialized successfully")
#     else:
#         OPENAI_AVAILABLE = False
#         print("Warning: OpenAI API key not set or invalid. Using fallback generation.")
# except Exception as e:
#     OPENAI_AVAILABLE = False
#     print(f"Warning: Could not initialize OpenAI client: {e}. Using fallback generation.")


# def generate_text_data(prompt, num_rows=20, columns=None, model="gpt-3.5-turbo"):
#     """Generate synthetic text data using OpenAI or fallback method"""
    
#     # Check if OpenAI is available
#     if not OPENAI_AVAILABLE:
#         print("Using fallback text generation")
#         return generate_fallback_text_data(prompt, num_rows, columns)
    
#     try:
#         columns_str = f"The JSON should have these fields: {', '.join(columns)}." if columns else ""
#         messages = [
#             {
#                 "role": "system",
#                 "content": "You are a helpful assistant that generates realistic synthetic datasets. Return the data as a JSON array of objects. Each object should represent one row of data."
#             },
#             {
#                 "role": "user",
#                 "content": f"{prompt}. {columns_str} Generate exactly {num_rows} rows as a JSON array. Each row should be an object with the specified fields. Do not include any explanation, just return the JSON array."
#             }
#         ]

#         print(f"Making OpenAI API call with prompt: {prompt[:50]}...")
#         response = client.chat.completions.create(
#             model=model,
#             messages=messages,
#             temperature=0.7
#         )

#         # Parse the response as JSON
#         try:
#             content = response.choices[0].message.content
#             print(f"OpenAI response received: {content[:100]}...")
#             json_data = json.loads(content)
#             return json_data
#         except json.JSONDecodeError as e:
#             print(f"JSON decode error: {e}")
#             print(f"Raw response: {content}")
#             return generate_fallback_text_data(prompt, num_rows, columns)
            
#     except Exception as e:
#         print(f"OpenAI API error: {e}")
#         return generate_fallback_text_data(prompt, num_rows, columns)


# def generate_fallback_text_data(prompt, num_rows, columns):
#     """Fallback text generation when OpenAI is not available"""
#     print("Generating fallback data")
#     if not columns:
#         columns = ["text", "category", "rating"]
    
#     # Generate sample data based on the prompt
#     sample_data = []
#     for i in range(num_rows):
#         row_data = {}
#         for col in columns:
#             if "review" in col.lower() or "text" in col.lower():
#                 row_data[col] = f"Sample {col} content for row {i+1}"
#             elif "rating" in col.lower():
#                 row_data[col] = (i % 5) + 1  # Ratings 1-5
#             elif "name" in col.lower():
#                 row_data[col] = f"User_{i+1}"
#             elif "category" in col.lower():
#                 row_data[col] = "Sample Category"
#             else:
#                 row_data[col] = f"Sample {col} value {i+1}"
#         sample_data.append(row_data)
    
#     return sample_data

# # Example prompt
# if __name__ == "__main__":
#     user_prompt = input("Enter your synthetic dataset prompt: ")
#     num_rows = int(input("Enter the number of rows to generate: "))
#     columns_input = input("Enter the column names (comma-separated): ")
#     columns = [col.strip() for col in columns_input.split(",") if col.strip()]
#     json_data = generate_text_data(user_prompt, num_rows=num_rows, columns=columns)
#     print(json.dumps(json_data, indent=2))
#     with open("synthetic_data.json", "w", encoding="utf-8") as f:
#         json.dump(json_data, f, indent=2)

# '''Generate a dataset of reviews for beauty products from sephora.com'''

import os
import openai
from openai import OpenAI
import pandas as pd
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_text_data(prompt, num_rows=20, columns=None, model="gpt-3.5-turbo"):
    columns_str = f"The CSV columns should be: {', '.join(columns)}." if columns else ""
    
    # Generate data in chunks to ensure we get exactly the requested number of rows
    chunk_size = min(100, num_rows)  # Generate in chunks of 100 or less
    all_data_rows = []
    header_row = None
    
    for chunk_start in range(0, num_rows, chunk_size):
        chunk_end = min(chunk_start + chunk_size, num_rows)
        current_chunk_size = chunk_end - chunk_start
        
        # Different prompts for first chunk vs subsequent chunks
        if chunk_start == 0:
            # First chunk: include header
            messages = [
                {
                    "role": "system",
                    "content": "You are a data generator that creates CSV datasets. Return ONLY the CSV data with headers and rows. Do not include any explanatory text, introductions, or conclusions. Start directly with the header row and end with the last data row."
                },
                {
                    "role": "user",
                    "content": f"{prompt}. {columns_str} Generate EXACTLY {current_chunk_size} data rows in CSV format. Include the header row first, then exactly {current_chunk_size} data rows. Return ONLY the CSV data starting with headers and ending with the last row. No explanations or additional text."
                }
            ]
        else:
            # Subsequent chunks: NO header, only data rows
            messages = [
                {
                    "role": "system",
                    "content": "You are a data generator that creates CSV datasets. Return ONLY CSV data rows (NO headers). Do not include any explanatory text, introductions, or conclusions."
                },
                {
                    "role": "user",
                    "content": f"{prompt}. {columns_str} Generate EXACTLY {current_chunk_size} additional data rows in CSV format (NO headers, just data rows). Return ONLY the data rows, no explanations or headers."
                }
            ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )

        content = response.choices[0].message.content
        
        # Parse the content
        lines = content.strip().split('\n')
        data_rows = [line for line in lines if line.strip() and not line.startswith('#')]
        
        if not data_rows:
            continue
            
        # Extract header and data rows
        if header_row is None:
            header_row = data_rows[0]
            data_rows = data_rows[1:]  # Remove header from data rows
        
        # Add only the data rows (skip header for subsequent chunks)
        all_data_rows.extend(data_rows)
    
    # Ensure we have exactly the requested number of rows
    if len(all_data_rows) > num_rows:
        all_data_rows = all_data_rows[:num_rows]
    elif len(all_data_rows) < num_rows:
        # Generate additional rows if we're short
        remaining = num_rows - len(all_data_rows)
        messages = [
            {
                "role": "system",
                "content": "You are a data generator that creates CSV datasets. Return ONLY the CSV data rows (no headers). Do not include any explanatory text."
            },
            {
                "role": "user",
                "content": f"{prompt}. {columns_str} Generate EXACTLY {remaining} additional data rows in CSV format (no headers, just data rows). Return ONLY the data rows, no explanations."
            }
        ]
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        
        additional_content = response.choices[0].message.content
        additional_lines = [line for line in additional_content.strip().split('\n') if line.strip() and not line.startswith('#')]
        all_data_rows.extend(additional_lines[:remaining])
    
    # Combine header and data rows
    if header_row:
        return header_row + '\n' + '\n'.join(all_data_rows[:num_rows])
    else:
        return '\n'.join(all_data_rows[:num_rows])

# Example prompt
if __name__  == "__main__":
    user_prompt = input("Enter your synthetic dataset prompt: ")
    num_rows = int(input("Enter the number of rows to generate: "))
    columns_input = input("Enter the column names (comma-separated): ")
    columns = [col.strip() for col in columns_input.split(",") if col.strip()]
    csv_data = generate_text_data(user_prompt, num_rows=num_rows, columns=columns)
    print(csv_data)
    with open("synthetic_reviews.csv", "w", encoding="utf-8") as f:
        f.write(csv_data)

'''Generate a dataset of reviews for beauty products from sephora.com'''

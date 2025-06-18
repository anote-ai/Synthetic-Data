import openai
import json

# Set your API key
openai.api_key = "INSERT_YOUR_OPENAI_KEY"
print("Using API key:", openai.api_key[:10])

# Get user prompt
user_prompt = input("Enter your synthetic dataset prompt: ")

try:
    prompt = f"High-quality illustration of a synthetic data task: {user_prompt}, use theme colors: #111827, #DEFE47, #28B2FB, white"

    response = openai.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )

    image_url = response.data[0].url
    print(f"Generated image URL: {image_url}")

    # Save result to JSON file
    with open("image_output.json", "w", encoding="utf-8") as f:
        json.dump({"prompt": user_prompt, "image": image_url}, f, indent=2)

except Exception as e:
    print("Error generating image:", str(e))

```py
from anote_generate import AnoteGenerate

sdk = AnoteGenerate(api_key="your-api-key")

result = sdk.generate(
    task_type="text",
    prompt="Generate sarcastic responses to common office phrases.",
    num_rows=3,
    columns=["phrase", "sarcastic_response"],
    examples=[
        {"phrase": "Let's circle back on this.", "sarcastic_response": "Sure, how about never?"},
        {"phrase": "Think outside the box.", "sarcastic_response": "I live outside the box."}
    ]
)

print(result)
```

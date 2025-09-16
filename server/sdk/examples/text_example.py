import sys
import os
# from api_key_constants import TOMMY_API_KEY, NATAN_API_KEY, TOMMY_DIRECTORY, NATAN_DIRECTORY

# Define the directory of core.py
core_directory = os.path.join(os.path.dirname(__file__), "..")

# Add the directory to the sys.path
if core_directory not in sys.path:
    sys.path.append(core_directory)

from anotegenerate.core import AnoteGenerate

# Use a test API key (replace with your actual API key)
api_key = "1234567890"  # Replace with your actual API key

# Initialize the SDK
# For production, you can either:
# 1. Use default production URL (no base_url parameter needed)
# 2. Set environment variable: export ANOTE_API_BASE_URL="https://api.anote.ai"
# 3. Pass base_url explicitly: AnoteGenerate(api_key=api_key, base_url="https://api.anote.ai")
# 4. For local development: AnoteGenerate(api_key=api_key, base_url="http://localhost:5000")

sdk = AnoteGenerate(api_key=api_key)  # Uses production URL by default

# Generate customer support conversations
result = sdk.generate(
    task_type="text",
    prompt="Generate customer support conversations about product issues",
    num_rows=5,
    columns=["customer_message", "agent_response", "issue_type", "resolution"]
)

print(result)
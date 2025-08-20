import sys
import os
# from api_key_constants import

core_directory = "C:/Users/HP/Desktop/PROJECTS/Anote-SyntheticData/server/sdk"

# Add the directory to the sys.path
if core_directory not in sys.path:
    sys.path.append(core_directory)


from anotegenerate.core import AnoteGenerate

sdk = AnoteGenerate(api_key="1234567890")

# Generate customer support conversations
result = sdk.generate(
    task_type="text",
    prompt="Generate customer support conversations about product issues",
    num_rows=5,
    columns=["customer_message", "agent_response", "issue_type", "resolution"]
)

print(result)
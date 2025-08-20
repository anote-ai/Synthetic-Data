import requests
import json

class AnoteGenerate:
    def __init__(self, api_key):
        self.API_BASE_URL = 'http://localhost:5000'
        # self.API_BASE_URL = "https://api.anote.ai"
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def generate(self, task_type: str, columns: list, prompt: str = None, num_rows: int = 10, examples: list = None):
        """
        Generate synthetic data based on task type and prompt.

        Args:
            task_type (str): One of ['text', 'image', 'video', 'audio', 'agent', 'reasoning']
            columns (list): Column names for dataset
            prompt (str, optional): Prompt to guide generation
            num_rows (int, optional): Number of data rows to generate
            examples (list, optional): Few-shot examples to guide generation

        Returns:
            dict: Generated dataset in JSON or downloadable CSV format
        """
        data = {
            "task_type": task_type,
            "prompt": prompt,
            "num_rows": num_rows,
            "columns": columns,
            "examples": examples
        }

        response = requests.post(f"{self.API_BASE_URL}/public/generate", headers=self.headers, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Generation failed with status code {response.status_code}: {response.text}")
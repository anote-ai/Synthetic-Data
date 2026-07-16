import csv
import io


def dataset_csv(rows):
    if not rows:
        return ""
    columns = [column for column in rows[0] if column != "status"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def dataset_card(name, rows, prompt, task_category="text-classification", language="en"):
    columns = [column for column in rows[0] if column != "status"] if rows else []
    return f"""---
task_categories:
- {task_category}
language:
- {language}
---
# {name.split('/')[-1]}

Generated with Anote Synthetic Data.

**Prompt:** {prompt}

**Rows:** {len(rows)} | **Columns:** {', '.join(columns)}
"""


def push_dataset(token, repo_id, private, rows, prompt, task_category, language):
    from huggingface_hub import CommitOperationAdd, HfApi

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    csv_bytes = dataset_csv(rows).encode("utf-8")
    card_bytes = dataset_card(repo_id, rows, prompt, task_category, language).encode("utf-8")
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Upload dataset from Anote Synthetic Data",
        operations=[
            CommitOperationAdd(path_in_repo="data.csv", path_or_fileobj=csv_bytes),
            CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=card_bytes),
        ],
    )
    return f"https://huggingface.co/datasets/{repo_id}"

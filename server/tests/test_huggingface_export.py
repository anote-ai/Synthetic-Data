from utils.huggingface_export import dataset_card, dataset_csv


def test_dataset_csv_excludes_internal_status_column():
    output = dataset_csv([{"text": "hello, world", "label": "greeting", "status": "ok"}])
    assert output.splitlines()[0] == "text,label"
    assert '"hello, world",greeting' in output


def test_dataset_card_contains_hub_metadata_and_generation_context():
    output = dataset_card(
        "alice/support-tickets",
        [{"text": "Help", "label": "support"}],
        "Generate support tickets",
        "text-classification",
        "en",
    )
    assert "task_categories:\n- text-classification" in output
    assert "# support-tickets" in output
    assert "**Rows:** 1 | **Columns:** text, label" in output
    assert "Generate support tickets" in output

def generate_text_data(prompt, columns, num_rows, examples):
    results = []
    for i in range(num_rows):
        row = {col: f"Generated {col} value {i}" for col in columns}
        results.append(row)
    return results

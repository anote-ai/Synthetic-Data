import sys
import os
from api_key_constants import TOMMY_API_KEY, NATAN_API_KEY, TOMMY_DIRECTORY, NATAN_DIRECTORY

# Define the directory of core.py
core_directory = TOMMY_DIRECTORY

# Add the directory to the sys.path
if core_directory not in sys.path:
    sys.path.append(core_directory)

import pandas as pd
from core import Anote
from constants import NLPTask, ModelType, EvaluationMetric
from time import sleep

api_key = TOMMY_API_KEY

# Initialize the Anote class
anote = Anote(api_key)

# TODO: Uncomment train once it works.
# Training the NER model on the dataset
# train_response = anote.train(
#     task_type=NLPTask.NAMED_ENTITY_RECOGNITION,
#     model_type=ModelType.FEW_SHOT_NAMED_ENTITY_RECOGNITION,
#     dataset_name="TRAIN_NER",
#     multi_column_roots=[{"actualLabelColIndex": 1}],
#     input_text_col_index=0,  # List of input text column names
#     document_files=["./example_data/NER_data/TRAIN_NER.csv"]
# )

# TODO: Sub in your own model ID and dataset ID to get it to work.
# modelId = train_response["models"][0]["id"]
modelId = 67
# datasetId = train_response["datasetId"]
datasetId = 82
print(f"Trained NER model ID: {modelId}")
print(f"Dataset ID: {datasetId}")

# Check training status
while True:
    train_status_response = anote.checkStatus(
        model_id=modelId,
    )
    if train_status_response["isComplete"] == True:
        print("NER model training complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# Making predictions on the test dataset
predict_all_response = anote.predictAll(
    model_id=modelId,
    model_types=[],
    dataset_id=datasetId,
    report_name="NER report",
    input_text_col_index=0,
    actual_label_col_index=1,
    document_files=["./example_data/NER_data/TEST_NER.csv"]
)

print("NER Predictions:", predict_all_response)
predictReportId = predict_all_response["predictReportId"]

# Check prediction status
while True:
    preds_status_response = anote.checkStatus(
        predict_report_id=predictReportId,
    )
    if preds_status_response["isComplete"] == True:
        print("NER predictions complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# View predictions
predictions = anote.viewPredictions(
    predict_report_id=predictReportId,
    dataset_id=datasetId,
    search_query=None,
    page_number=1
)
print("NER predictions: ", predictions)

# Making a single prediction
single_prediction = anote.predict(
    model_id=modelId,
    text="Barack Obama was born in Hawaii.",
    document_files=None  # No additional documents required for single prediction
)

print("Single Prediction:", single_prediction)

# Evaluating the NER model with the testing document
evaluation_results = anote.evaluate(
    metrics=['precision', 'accuracy', 'recall', 'f1_score'],
    multi_column_roots=[
        {
            "actualLabelColIndex": 1,
            "modelPredictions": [2],
        }
    ],
    input_text_col_index=0,
    document_files=["./example_data/NER_data/TEST_NER.csv"],
    task_type=NLPTask.NAMED_ENTITY_RECOGNITION,
    report_name="NER evaluation report",
)

print("NER Evaluation Results:", evaluation_results)
evalReportId = evaluation_results["predictReportId"]

# Check evaluation status
while True:
    evals_status_response = anote.checkStatus(
        predict_report_id=evalReportId,
    )
    if evals_status_response["isComplete"] == True:
        print("NER evaluation complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# View evaluation predictions
evals = anote.viewPredictions(
    predict_report_id=evalReportId,
    dataset_id=datasetId,
    search_query=None,
    page_number=1
)
print("Evaluation predictions: ", evals)
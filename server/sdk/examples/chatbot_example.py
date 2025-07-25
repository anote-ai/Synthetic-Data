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

# Example use of TRAIN for Chatbot
train_response = anote.train(
    task_type=NLPTask.CHATBOT,
    model_type=ModelType.PROMPTING_WITH_FEEDBACK_PROMPT_ENGINEERED,
    dataset_name="TRAIN_CHATBOT",
    multi_column_roots=[{"actualLabelColIndex": 1}],
    input_text_col_index=0,
    document_files=[
        "./example_data/chatbot_data/TRAIN_CHATBOT.csv",
        "./example_data/chatbot_data/document_bank_doc_1.txt",
        "./example_data/chatbot_data/document_bank_doc_2.txt"
    ]
)

modelId = train_response["models"][0]["id"]
datasetId = train_response["datasetId"]
# modelId = 76
# datasetId = 92
print(f"Trained chatbot model ID: {modelId}")
print(f"Dataset ID: {datasetId}")

# Check training status
while True:
    train_status_response = anote.checkStatus(
        model_id=modelId,
    )
    if train_status_response["isComplete"] == True:
        print("Chatbot model training complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# Example use of PREDICT for Chatbot
predict_all_response = anote.predictAll(
    model_id=modelId,
    model_types=[],
    dataset_id=datasetId,
    report_name="chatbot_report",
    input_text_col_index=0,
    actual_label_col_index=1,
    document_files=[
        "./example_data/chatbot_data/TEST_CHATBOT.csv",
        "./example_data/chatbot_data/document_bank_doc_1.txt",
        "./example_data/chatbot_data/document_bank_doc_2.txt"
    ]
)
print("Chatbot Predictions:", predict_all_response)

predictReportId = predict_all_response["predictReportId"]

# Check prediction status
while True:
    preds_status_response = anote.checkStatus(
        predict_report_id=predictReportId,
    )
    if preds_status_response["isComplete"] == True:
        print("Chatbot predictions complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# View predictions
predictions = anote.viewPredictions(
    predict_report_id=predictReportId,
    search_query=None,
    dataset_id=datasetId,
    page_number=1
)
print("Chatbot Predictions: ", predictions)

# Example use of PREDICT for a single input
single_input = "Hello, how are you?"
single_prediction = anote.predict(
    model_id=modelId,
    text=single_input
)
print("Single Chatbot Prediction:", single_prediction)

# Example use of EVALUATE for Chatbot
evaluation_results = anote.evaluate(
    metrics=['faithfulness', 'answer_relevance'],
    multi_column_roots=[
        {
            "actualLabelColIndex": 1,
            "modelPredictions": [2],
        }
    ],
    input_text_col_index=0,
    document_files=["./example_data/chatbot_data/TEST_CHATBOT.csv"],
    task_type=NLPTask.CHATBOT,
    report_name="chatbot_evaluation_report",
)
print("Chatbot Evaluation Results:", evaluation_results)

evalReportId = evaluation_results["predictReportId"]

# Check evaluation status
while True:
    evals_status_response = anote.checkStatus(
        predict_report_id=evalReportId,
    )
    if evals_status_response["isComplete"] == True:
        print("Chatbot evaluation complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# View evaluation predictions
evals = anote.viewPredictions(
    predict_report_id=evalReportId,
    search_query=None,
    dataset_id=datasetId,
    page_number=1
)
print("Evaluation Predictions: ", evals)

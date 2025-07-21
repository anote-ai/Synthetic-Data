import sys
import os
from api_key_constants import TOMMY_API_KEY, NATAN_API_KEY, TOMMY_DIRECTORY, NATAN_DIRECTORY

core_directory = TOMMY_DIRECTORY

# Add the directory to the sys.path
if core_directory not in sys.path:
    sys.path.append(core_directory)

import pandas as pd
from anoteai import Anote
from constants import NLPTask, ModelType, EvaluationMetric
from time import sleep

api_key = TOMMY_API_KEY

# Initialize the Anote class
anote = Anote(api_key)

def _generate_sample_hierarchical_data():
    df = pd.read_csv("./example_data/hierarchical_data/HIERARCHICAL_TEXT.csv")
    taxonomy_df = pd.read_csv("./example_data/hierarchical_data/HIERARCHICAL_TAXONOMY.csv")
    df["Category"] = taxonomy_df["Category"][:len(df)]
    df["Sub-Category"] = taxonomy_df["Sub-Category"][:len(df)]
    hierarchical_train_df = df[:25]
    hierarchical_test_df = df[25:]
    hierarchical_train_df.to_csv("./example_data/hierarchical_data/TRAIN_HIERARCHICAL_CLASSIFICATION.csv")
    hierarchical_test_df.to_csv("./example_data/hierarchical_data/TEST_HIERARCHICAL_CLASSIFICATION.csv")
_generate_sample_hierarchical_data()

# Training the model on training dataset
train_response = anote.train(
    task_type=NLPTask.TEXT_CLASSIFICATION,
    model_type=ModelType.NAIVE_BAYES_TEXT_CLASSIFICATION,
    dataset_name="TRAIN_TEXT_CLASSIFICATION",
    multi_column_roots=[{"actualLabelColIndex": 1}, {"actualLabelColIndex": 2}],
    input_text_col_index=0,  # List of input text column names
    document_files=["./example_data/hierarchical_data/TRAIN_HIERARCHICAL_CLASSIFICATION.csv"]
)
modelId = train_response["models"][0]["id"]
datasetId = train_response["datasetId"]
print(f"Trained model ID: {modelId}")
print(f"Dataset ID: {datasetId}")

while True:
    train_status_response = anote.checkStatus(
        model_id=modelId,
    )
    if train_status_response["isComplete"] == True:
        print("trained model complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# Making predictions on the test dataset with the document file
predict_all_response = anote.predictAll(
    model_id=modelId,
    # model_types=[ZeroShotModelType.ZEROSHOT_GPT4],
    model_types=[],
    dataset_id=datasetId,
    report_name="report 123",
    input_text_col_index=0,
    actual_label_col_index=1,
    document_files=["./example_data/hierarchical_data/TEST_HIERARCHICAL_CLASSIFICATION.csv"]  # Path to the testing document file
)

print("Predictions:", predict_all_response)
predictReportId = predict_all_response["predictReportId"]

while True:
    preds_status_response = anote.checkStatus(
        predict_report_id=predictReportId,
    )
    if preds_status_response["isComplete"] == True:
        print("predictions complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

# Making a single prediction
predictions = anote.viewPredictions(
    predict_report_id=predictReportId,
    dataset_id=datasetId,
    search_query=None,
    page_number=1
)
print("predictions: ", predictions)

# Making a single prediction
single_prediction = anote.predict(
    model_id=modelId,
    text="I love good weather",
    document_files=None  # No additional documents required for single prediction
)

print("Single Prediction:", single_prediction)
# Evaluating the model with the testing document
evaluation_results = anote.evaluate(
    metrics=['precision', 'accuracy', 'recall', 'f1_score'],
    multi_column_roots=[
        {
            "actualLabelColIndex": 1,
            "modelPredictions": [2],
        }
    ],
    input_text_col_index=0,
    document_files=["./example_data/hierarchical_classification/TEST_HIERARCHICAL_CLASSIFICATION.csv"],
    task_type=NLPTask.TEXT_CLASSIFICATION,
    report_name="report 321",
)

print("Evaluation Results:", evaluation_results)
evalReportId = evaluation_results["predictReportId"]

while True:
    evals_status_response = anote.checkStatus(
        predict_report_id=evalReportId,
    )
    if evals_status_response["isComplete"] == True:
        print("trained model complete...")
        break
    else:
        print("sleeping...")
        sleep(3)
        print("trying again...")

evals = anote.viewPredictions(
    predict_report_id=evalReportId,
    dataset_id=datasetId,
    search_query=None,
    page_number=1
)
print("predictions: ", evals)
Overview

This repository contains one synthetic dataset created for evaluating Named Entity Recognition (NER) models.
These datasets are designed for use in information extraction, data labeling research, and model evaluation
in domains involving personally identifiable information (PII).

Dataset Files

1. synthetic_example.jsonl

Format: JSON Lines
Encoding: UTF-8
Structure: Each line is a JSON object representing a single annotated document.

Fields:
- text: The full paragraph of synthetic content
- entities: A list of [start_index, end_index, label] indicating the span and type of each recognized entity


Example Entity Types
--------------------
Label       | Description
------------|-------------------------------
MRN         | Medical Record Number
PLATE       | Vehicle License Plate
BIO         | Biometric or user ID-like token
VIN         | Vehicle Identification Number
PASSPORT    | Passport Number
EMP         | Employee ID
IP          | IP Address
CREDIT      | Credit Card or Account Number

                
2. output.csv

Format: CSV (Comma-Separated Values)
Encoding: UTF-8
Headers: Included in the first row

Fields:
- Sentence: A synthetic paragraph containing personal and identifying information
- Ground Truth Entities: List of (text, label) tuples representing true entity annotations
- Model Predicted Entities: List of predicted (text, label) tuples from a model
- Precision: Precision score of model prediction
- Recall: Recall score of model prediction
- F1 Score: F1 score of model prediction
- IoU: Intersection-over-Union metric between ground truth and prediction

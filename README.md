**Range of Synthetic Data Generation Tasks**

**Text:**
Classification: For example, generating Amazon movie reviews labeled with positive, negative, or neutral sentiment. This involves creating both the documents and their corresponding categories.
Named Entity Recognition (NER): For example, extracting personally identifiable information (PII) from documents. This task involves generating text with labeled entities.
Chatbot: For example, creating a Japanese language training dataset for conversational agents.
Prompting / Information Extraction: For example, extracting structured information from unstructured 10-K financial reports.


**Images:** Object Detection: For example, detecting and annotating bounding boxes in undersea imaging. An example reference is the Anote Bluetide evaluation documentation: https://docs.anote.ai/bluetide/evaluate.html
Image Generation: For example, generating training data for image generation models like DALL-E, where synthetic images are created from text prompts.


**Video:**
Training Data: For example, creating training data for video generation models such as Veo3 or Sora, which require labeled or structured video sequences.


**Audio:**
Training Data: For example, generating synthetic audio for training models like Suno or Eleven Labs. This can include voice synthesis or speech recognition datasets.


**Agents:**
Training Data for Agents: For example, generating data to train agents that perform tasks using browsers, operating systems, or in multi-agent environments. This includes sequences of user or system interactions.


This directory contains comprehensive examples demonstrating how to use the SyntheticDataGen API across different data modalities and use cases.

## 📁 Directory Structure - Types of Generators 
- **text/**: Text-based dataset generation examples
- **images/**: Image dataset generation and annotation
- **video/**: Video dataset creation examples  
- **audio/**: Audio dataset generation examples
- **agents/**: Agent behavior dataset examples
- **evaluation/**: Dataset evaluation and benchmarking

## 🚀 Getting Started
Each example is self-contained and includes:
- Complete working code
- Detailed documentation
- Quality validation steps
- Performance evaluation
- Best practices and tips

## 🔧 Setup

```bash
# Install required dependencies
pip install -r ../requirements.txt

# Set up API credentials
export SYNTHETIC_DATA_API_KEY="your_api_key"
export OPENAI_API_KEY="your_openai_key"  # For LLM generation
```

## 📊 Quality Assurance Examples

Each example demonstrates our multi-layered quality approach:
1. Heuristic validation
2. AI-powered review
3. Iterative refinement
4. Benchmark comparison






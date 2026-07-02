# Setup

## Installation

Install the SDK from PyPI:

```bash
pip install anote-generate
```

### Authentication
All API calls require an API key. To get your API key, register at https://anote.ai and navigate to your account settings.

### Initialization

```python
from anote_generate import Anote

api_key = "your-api-key"
sdk = Anote(api_key=api_key)
```

**Dependencies**
The SDK requires Python 3.9+ and depends on the following libraries:

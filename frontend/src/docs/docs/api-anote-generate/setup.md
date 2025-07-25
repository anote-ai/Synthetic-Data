# Setup

## Installation

Install the SDK from PyPI:

```bash
pip install anote-generate
```

### Authentication
All API calls require an API key. To get your API key, register at https://anote.ai and navigate to your account settings.

### Initialization

```
from anotegenerate.core import AnoteGenerate

api_key = "your-api-key"
sdk = AnoteGenerate(api_key=api_key)
```

**Dependencies**
The SDK requires Python 3.7+ and depends on the following libraries:



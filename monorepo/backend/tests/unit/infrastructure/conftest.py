import sys
from unittest.mock import MagicMock

# Stub heavy external libraries that are not installed in the unit test
# environment. These modules are only needed in production (GPU/infra).
# Stubs must be registered before any test module is imported.
_stubs = [
    "sentence_transformers",
    "qdrant_client",
    "qdrant_client.http",
    "qdrant_client.http.models",
    "qdrant_client.models",
]
for _name in _stubs:
    sys.modules.setdefault(_name, MagicMock())

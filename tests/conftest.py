import inspect
import os
from unittest.mock import MagicMock

import google.auth
import google.auth.exceptions
import google.cloud.logging
import vertexai
from google.auth.credentials import AnonymousCredentials

# Set dummy Google Cloud environments
os.environ["GOOGLE_CLOUD_PROJECT"] = "dummy-project"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
os.environ["INTEGRATION_TEST"] = "TRUE"

# Save original default authentication loader
original_default = google.auth.default


def mock_default(*args, **kwargs):
    # Dynamically inspect caller stack
    stack = inspect.stack()
    for frame_info in stack:
        module_name = frame_info.frame.f_globals.get("__name__", "")
        filename = frame_info.filename
        # Check if caller is part of google.genai client libraries
        if (
            "google/genai" in filename.replace("\\", "/")
            or "google.genai" in module_name
        ):
            raise google.auth.exceptions.DefaultCredentialsError(
                "Skipping default credentials for Gemini API Client"
            )

    # Return dummy credentials for other (Vertex/telemetry) SDK operations
    return AnonymousCredentials(), "dummy-project"


# Override default authentication
google.auth.default = mock_default

# Initialize vertexai with dummy project and credentials to prevent default auth lookup
vertexai.init(
    project="dummy-project", location="us-central1", credentials=AnonymousCredentials()
)

# Mock google.cloud.logging.Client to avoid GCP Logging API calls
google.cloud.logging.Client = MagicMock()

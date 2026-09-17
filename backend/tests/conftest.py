import os

# Set dummy AWS credentials and region for local testing
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "mock-key-id"
os.environ["AWS_SECRET_ACCESS_KEY"] = "mock-secret-key"
os.environ["PROJECTS_TABLE"] = "ProjectsTable"
os.environ["CONFLICTS_TABLE"] = "ConflictsTable"
os.environ["UPLOAD_BUCKET"] = "crosscheck-uploads"

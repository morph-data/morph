import os

import morph
from morph import MorphGlobalContext


# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# For more information: https://docs.morph-data.io
@morph.func(
    name="file_upload",
)
@morph.variables("file")
def file_upload(context: MorphGlobalContext) -> str:
    # Retrieve the `file` variable from the context (Expand `~` to the full path)
    filepath = os.path.expanduser(context.vars["file"])
    filename = os.path.basename(filepath)

    # Check if the file exists
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # Create the uploaded-files directory if it doesn't exist
    # NOTE: Make sure to use an absolute path for the directory
    upload_dir = os.path.abspath("uploaded-files/")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    # Read the content of the file in binary mode
    with open(filepath, "rb") as f:
        file_content = f.read()

    # Save the content to the uploaded-files directory in binary mode
    saved_filepath = os.path.join(upload_dir, filename)
    with open(saved_filepath, "wb") as f:
        f.write(file_content)

    return saved_filepath

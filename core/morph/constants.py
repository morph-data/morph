import os


class MorphConstant:
    # Directories
    INIT_DIR = os.path.expanduser("~/.morph")
    TMP_MORPH_DIR = "/tmp/morph"
    # Files
    MORPH_CRED_PATH = os.path.expanduser("~/.morph/credentials")
    MORPH_CONNECTION_PATH = os.path.expanduser("~/.morph/connections.yml")
    # Others
    EXECUTABLE_EXTENSIONS = [".sql", ".py"]

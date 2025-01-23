import base64
import logging
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel

from morph.constants import MorphConstant

IGNORE_DIRS = ["/private/tmp", "/tmp"]


def find_project_root_dir(abs_filepath: Optional[str] = None) -> str:
    current_dir = (
        abs_filepath if abs_filepath and os.path.isabs(abs_filepath) else os.getcwd()
    )

    for ignore_dir in IGNORE_DIRS:
        if ignore_dir in current_dir:
            current_dir = os.getcwd()

    project_yaml_files = ["morph_project.yml", "morph_project.yaml"]
    while current_dir != os.path.dirname(current_dir):
        for project_yaml_file in project_yaml_files:
            if os.path.isfile(os.path.join(current_dir, project_yaml_file)):
                return os.path.abspath(current_dir)
        current_dir = os.path.dirname(current_dir)

    morph_project_path = os.path.join(Path.home(), "morph_project.yml")
    if os.path.isfile(morph_project_path):
        return os.path.abspath(os.path.dirname(morph_project_path))
    morph_project_path = os.path.join(Path.home(), "morph_project.yaml")
    if os.path.isfile(morph_project_path):
        return os.path.abspath(os.path.dirname(morph_project_path))

    raise FileNotFoundError(
        "morph_project.yml not found in the current directory or any parent directories."
    )


def initialize_frontend_dir(project_root: str) -> str:
    """
    Initialize the frontend directory by copying the template frontend directory to the project directory.
    Does nothing if the frontend directory already exists.
    @param project_root:
    @return:
    """
    frontend_template_dir = os.path.join(
        Path(__file__).resolve().parents[2], "frontend", "template"
    )
    frontend_dir = MorphConstant.frontend_dir(project_root)
    if not os.path.exists(frontend_dir):
        os.makedirs(frontend_dir, exist_ok=True)
        shutil.copytree(frontend_template_dir, frontend_dir, dirs_exist_ok=True)
    return frontend_dir


class Resource(BaseModel):
    alias: str
    path: str
    connection: Optional[str] = None
    output_paths: Optional[List[str]] = None
    public: Optional[bool] = None
    output_type: Optional[str] = None
    data_requirements: Optional[List[str]] = None

    def __init__(
        self,
        alias: str,
        path: str,
        connection: Optional[str] = None,
        output_paths: Optional[List[str]] = None,
        public: Optional[bool] = None,
        output_type: Optional[str] = None,
        data_requirements: Optional[List[str]] = None,
    ):
        super().__init__(
            alias=alias,
            path=path,
            connection=connection,
            output_paths=output_paths,
            public=public,
            output_type=output_type,
            data_requirements=data_requirements,
        )

        # Add attributes for executable files
        ext = os.path.splitext(path)[1]
        if ext in MorphConstant.EXECUTABLE_EXTENSIONS:
            self.connection = connection
            self.output_paths = output_paths
        else:
            self.connection = None
            self.output_paths = None

    def _replace_output_placeholders(
        self,
        run_id: str,
        output_file: str,
        logger: logging.Logger = logging.getLogger(),
    ) -> List[str]:
        # Definition of placeholder functions that can be used in the output_path
        placeholder_map: Dict[str, str] = {
            "{run_id}": run_id,
            "{name}": self.alias,
            "{now()}": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "{unix()}": str(int(time.time() * 1000)),
        }

        # Replace placeholders in the output path
        for placeholder, expanded in placeholder_map.items():
            if placeholder in output_file:
                output_file = output_file.replace(placeholder, expanded)

        # Replace ext() placeholder; ext() can produce multiple output_paths
        output_files: List[str] = []
        if "{ext()}" in output_file:
            extensions = [".txt"]
            if self.output_type == "visualization":
                extensions = [".html", ".png"]
            elif self.output_type == "dataframe":
                extensions = [".parquet"]
            elif self.output_type == "csv":
                extensions = [".csv"]
            elif self.output_type == "markdown":
                extensions = [".md"]
            elif self.output_type == "json":
                extensions = [".json"]
            output_files = [output_file.replace("{ext()}", ext) for ext in extensions]
        else:
            output_files = [output_file]

        # Validate the output paths
        validated_outputs = []
        for f in output_files:
            # Check for undefined placeholders
            if "{" in f and "}" in f:
                logger.warning(
                    f"Unrecognized placeholder found in the output_paths: {f}. Cell output not saved."
                )
                continue
            validated_outputs.append(f)
        return validated_outputs

    @staticmethod
    def _write_output_file(
        output_file: str,
        output: Union[str, bytes],
    ) -> None:
        if not os.path.exists(os.path.dirname(output_file)):
            os.makedirs(os.path.dirname(output_file))

        if os.path.exists(output_file) and (
            output_file.startswith(MorphConstant.TMP_MORPH_DIR)
            or output_file.startswith("/private/tmp")
        ):
            os.unlink(output_file)

        mode = "wb" if isinstance(output, bytes) else "w"
        with open(output_file, mode) as f:
            f.write(output or "")

    def save_output_to_file(
        self,
        run_id: str,
        output: Union[str, bytes, List[Union[str, bytes]]],
        logger: logging.Logger = logging.getLogger(),
    ) -> "Resource":
        processed_output_paths = []

        for original_output_path in self.output_paths or []:
            output_files = self._replace_output_placeholders(
                run_id, original_output_path, logger
            )
            for output_file in output_files:
                if isinstance(output, list):
                    # For multiple outputs, HTML and PNG outputs are saved as files
                    for raw_output in output:
                        should_save_as_html = output_file.endswith(".html")
                        should_save_as_png = output_file.endswith(".png")

                        is_html_encoded = (
                            isinstance(raw_output, str)
                            and re.compile(r"<[^>]+>").search(raw_output) is not None
                        )
                        if should_save_as_html and not is_html_encoded:
                            continue

                        is_base64_encoded = (
                            isinstance(raw_output, str)
                            and re.match(r"^[A-Za-z0-9+/=]*$", raw_output) is not None
                        )
                        if should_save_as_png and not is_base64_encoded:
                            continue

                        if should_save_as_png:
                            base64.b64decode(raw_output, validate=True)
                            raw_output = base64.b64decode(raw_output)

                        self._write_output_file(output_file, raw_output)
                        processed_output_paths.append(output_file)
                        logger.info(
                            f"Cell output saved to: {str(Path(output_file).resolve())}"
                        )
                else:
                    self._write_output_file(output_file, output)
                    processed_output_paths.append(output_file)
                    logger.info(
                        f"Cell output saved to: {str(Path(output_file).resolve())}"
                    )

        self.output_paths = processed_output_paths
        return self

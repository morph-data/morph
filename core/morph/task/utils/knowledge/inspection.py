import hashlib
from pathlib import Path
from typing import Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel

from morph.task.utils.run_backend.errors import (
    MorphFunctionLoadError,
    MorphFunctionLoadErrorCategory,
)


class MorphKnowledgeMetaObjectSource(BaseModel):
    name: str
    connection: Optional[str] = None


class MorphKnowledgeMetaObjectGlossaryTerm(BaseModel):
    name: str
    description: str


class MorphKnowledgeMetaObjectSchemaGlossary(BaseModel):
    name: str
    term: str


class MorphKnowledgeMetaObjectSchema(BaseModel):
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    test: Optional[List[Literal["not_null", "unique"]]] = None
    glossary: Optional[List[MorphKnowledgeMetaObjectSchemaGlossary]] = None


class MorphKnowledgeMetaObject(BaseModel):
    id: str
    name: str
    type: Literal["datasource", "model", "glossary"]
    title: Optional[str] = None
    description: Optional[str] = None
    # only for datasource and model
    source: Optional[MorphKnowledgeMetaObjectSource] = None
    schemas: Optional[List[MorphKnowledgeMetaObjectSchema]] = None
    # only for glossary
    terms: Optional[List[MorphKnowledgeMetaObjectGlossaryTerm]] = None


class KnowledgeScanResult(BaseModel):
    spec: MorphKnowledgeMetaObject
    file_path: str
    checksum: str


class DirectoryKnowledgeScanResult(BaseModel):
    directory: str
    directory_checksums: Dict[str, str]
    items: List[KnowledgeScanResult]
    errors: List[MorphFunctionLoadError]


def get_checksum(path: Path) -> str:
    """get checksum of file or directory."""
    hash_func = hashlib.sha256()

    if path.is_file():
        with open(str(path), "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)

        return hash_func.hexdigest()
    elif path.is_dir():
        for file in sorted(path.glob("**/*")):
            if file.is_file() and (file.suffix == ".yml" or file.suffix == ".yaml"):
                with open(str(file), "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_func.update(chunk)

        return hash_func.hexdigest()
    else:
        raise ValueError(f"Path {path} is not a file or directory.")


def _import_knowledge_file(
    file_path: Path,
) -> tuple[List[KnowledgeScanResult], List[MorphFunctionLoadError]]:
    """import a knowledge file."""
    with open(file_path, "r") as f:
        yaml_data = yaml.load(f, Loader=yaml.FullLoader)
        if "knowledges" not in yaml_data:
            return [], [
                MorphFunctionLoadError(
                    category=MorphFunctionLoadErrorCategory.INVALID_SYNTAX,
                    file_path=file_path.as_posix(),
                    name="",
                    error="knowledges is not found in the file.",
                )
            ]
        results: list[KnowledgeScanResult] = []
        errors: list[MorphFunctionLoadError] = []
        for knowledge in yaml_data["knowledges"]:
            if "name" not in knowledge:
                errors.append(
                    MorphFunctionLoadError(
                        category=MorphFunctionLoadErrorCategory.MISSING_ALIAS,
                        file_path=file_path.as_posix(),
                        name="",
                        error="name is not found in the knowledge.",
                    )
                )
                continue
            if "type" not in knowledge:
                errors.append(
                    MorphFunctionLoadError(
                        category=MorphFunctionLoadErrorCategory.INVALID_SYNTAX,
                        file_path=file_path.as_posix(),
                        name=knowledge["name"],
                        error="type is not found in the knowledge.",
                    )
                )
                continue

            results.append(
                KnowledgeScanResult(
                    spec=MorphKnowledgeMetaObject(
                        id=f"{file_path}:{knowledge['name']}",
                        name=knowledge["name"],
                        type=knowledge["type"],
                        title=knowledge.get("title"),
                        description=knowledge.get("description"),
                        source=MorphKnowledgeMetaObjectSource(
                            name=knowledge["source"].get("name"),
                            connection=knowledge["source"].get("connection"),
                        )
                        if "source" in knowledge
                        else None,
                        schemas=[
                            MorphKnowledgeMetaObjectSchema(
                                name=schema["name"],
                                description=schema.get("description"),
                                type=schema.get("type"),
                                test=schema.get("test"),
                                glossary=[
                                    MorphKnowledgeMetaObjectSchemaGlossary(
                                        name=glossary["name"],
                                        term=glossary["term"],
                                    )
                                    for glossary in schema.get("glossary", [])
                                ]
                                if schema.get("glossary") is not None
                                else [],
                            )
                            for schema in knowledge.get("schemas", [])
                        ]
                        if knowledge.get("schemas", []) is not None
                        else [],
                        terms=[
                            MorphKnowledgeMetaObjectGlossaryTerm(
                                name=term["name"],
                                description=term["description"],
                            )
                            for term in knowledge.get("terms", [])
                        ]
                        if knowledge.get("terms", []) is not None
                        else [],
                    ),
                    file_path=file_path.as_posix(),
                    checksum=get_checksum(file_path),
                )
            )
        return results, errors


def import_files(
    directory: str, knowledge_paths: List[str]
) -> DirectoryKnowledgeScanResult:
    """import knowledge files."""
    p = Path(directory)
    results: list[KnowledgeScanResult] = []
    errors: list[MorphFunctionLoadError] = []
    ignore_dirs = [".local", ".git", ".venv", "__pycache__"]

    search_paths: list[Path] = []
    if len(knowledge_paths) == 0:
        search_paths.append(p)
    else:
        for knowledge_path in knowledge_paths:
            search_paths.append(p / knowledge_path)

    directory_checksums: dict[str, str] = {}
    for search_path in search_paths:
        for file in list(search_path.glob("**/*.yml")) + list(
            search_path.glob("**/*.yaml")
        ):
            if any(ignore_dir in file.parts for ignore_dir in ignore_dirs):
                continue

            scan_results, scan_errors = _import_knowledge_file(file)
            if scan_results is not None:
                results.extend(scan_results)
            if scan_errors is not None:
                errors.extend(scan_errors)

        directory_checksums[search_path.as_posix()] = get_checksum(search_path)

    return DirectoryKnowledgeScanResult(
        directory=directory,
        directory_checksums=directory_checksums,
        items=results,
        errors=errors,
    )

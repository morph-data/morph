from __future__ import annotations

import json
from pathlib import Path

from typing_extensions import Self

from morph.config.project import load_project
from morph.task.utils.knowledge.inspection import (
    DirectoryKnowledgeScanResult,
    KnowledgeScanResult,
    MorphKnowledgeMetaObjectSource,
    import_files,
)
from morph.task.utils.run_backend.errors import MorphFunctionLoadError


def _cache_path(directory: str) -> str:
    return f"{directory}/.morph/knowledge.json"


def load_cache(project_root: str) -> DirectoryKnowledgeScanResult | None:
    cache_path = _cache_path(project_root)
    if not Path(cache_path).exists():
        return None

    with open(cache_path, "r") as f:
        data = json.load(f)

    return DirectoryKnowledgeScanResult.model_validate(data)


def dump_cache(cache: DirectoryKnowledgeScanResult) -> None:
    cache_path = _cache_path(cache.directory)
    if not Path(cache_path).parent.exists():
        Path(cache_path).parent.mkdir(parents=True)

    with open(cache_path, "w") as f:
        json.dump(cache.model_dump(), f, indent=2)


class MorphKnowledgeManager:
    __scans: list[DirectoryKnowledgeScanResult]

    def __init__(self):
        self.__scans = []

    @classmethod
    def get_instance(cls) -> Self:
        if not hasattr(cls, "_instance"):
            cls._instance = cls()  # type: ignore
        return cls._instance  # type: ignore

    def find(self, name: str) -> KnowledgeScanResult | None:
        for scan in self.__scans:
            for item in scan.items:
                if item.spec.name == name:
                    return item
        return None

    def find_by_source(
        self, type: str, source: MorphKnowledgeMetaObjectSource
    ) -> KnowledgeScanResult | None:
        for scan in self.__scans:
            for item in scan.items:
                if (
                    item.spec.type == type
                    and item.spec.source is not None
                    and item.spec.source.name == source.name
                    and item.spec.source.connection == source.connection
                ):
                    return item
        return None

    def load(self, directory: str) -> list[MorphFunctionLoadError]:
        project = load_project(directory)
        if project is not None:
            knowledge_paths = project.knowledge_paths
        else:
            knowledge_paths = []

        result = import_files(directory, knowledge_paths)
        self.__scans.append(result)
        return result.errors

    def dump(self) -> DirectoryKnowledgeScanResult:
        if len(self.__scans) == 0:
            raise ValueError("No files are loaded.")

        scan = self.__scans[-1]
        cache_items: list[KnowledgeScanResult] = []
        for scan_item in scan.items:
            item = KnowledgeScanResult(
                spec=scan_item.spec,
                file_path=scan_item.file_path,
                checksum=scan_item.checksum,
            )
            cache_items.append(item)

        cache = DirectoryKnowledgeScanResult(
            directory=scan.directory,
            directory_checksums=scan.directory_checksums,
            items=cache_items,
            errors=scan.errors,
        )
        dump_cache(cache)
        return cache

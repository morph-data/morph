from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel
from typing_extensions import Self

from morph.api.cloud.types import UserInfo
from morph.api.context import request_context
from morph.config.project import MorphProject, load_project

from .errors import MorphFunctionLoadError, MorphFunctionLoadErrorCategory
from .inspection import (
    DirectoryScanResult,
    _import_python_file,
    _import_sql_file,
    get_checksum,
    import_files,
)


class MorphFunctionMetaObject(BaseModel):
    id: str
    name: str
    function: Optional[Callable[..., Any]]
    description: Optional[str] = None
    title: Optional[str] = None
    variables: Optional[Dict[str, Any]] = {}
    data_requirements: Optional[List[str]] = []
    connection: Optional[str] = None


class MorphFunctionMetaObjectCacheItem(BaseModel):
    spec: MorphFunctionMetaObject
    file_path: str
    checksum: str


class MorphFunctionMetaObjectCache(BaseModel):
    directory: str
    directory_checksums: dict[str, str]
    items: List[MorphFunctionMetaObjectCacheItem]
    errors: List[MorphFunctionLoadError]

    def find_by_name(self, name: str) -> MorphFunctionMetaObjectCacheItem | None:
        for item in self.items:
            if item.spec.name == name:
                return item
        return None


class MorphFunctionMetaObjectCacheManager:
    _instance: Optional["MorphFunctionMetaObjectCacheManager"] = None
    _cache: Optional["MorphFunctionMetaObjectCache"] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MorphFunctionMetaObjectCacheManager, cls).__new__(cls)
            cls._instance._cache = None
        return cls._instance

    def get_cache(self) -> MorphFunctionMetaObjectCache | None:
        return self._cache

    def set_cache(self, cache: MorphFunctionMetaObjectCache) -> None:
        self._cache = cache


class MorphGlobalContext:
    __data: dict[str, pd.DataFrame]
    __vars: dict[str, Any]
    __meta_objects: list[MorphFunctionMetaObject]
    __scans: list[DirectoryScanResult]

    def __init__(self):
        self.__data = {}
        self.__vars = {}
        self.__meta_objects = []
        self.__scans = []

    @classmethod
    def get_instance(cls) -> Self:
        if not hasattr(cls, "_instance"):
            cls._instance = cls()  # type: ignore
        return cls._instance  # type: ignore

    @property
    def data(self) -> dict[str, pd.DataFrame]:
        return self.__data

    @property
    def vars(self) -> dict[str, Any]:
        return self.__vars

    @property
    def user_info(self) -> Optional[Dict[str, Any]]:
        ctx = request_context.get()
        if ctx and "user" in ctx and ctx["user"]:
            return UserInfo.model_validate(ctx["user"]).model_dump()
        return None

    def load(self, directory: str) -> list[MorphFunctionLoadError]:
        project = load_project(directory)
        if project is not None:
            source_paths = project.source_paths
        else:
            source_paths = []

        extra_paths: List[str] = []

        cwd = str(Path.cwd().resolve())
        if cwd not in sys.path:
            sys.path.append(cwd)

        result = import_files(project, directory, source_paths, extra_paths)
        for key, value in result.sql_contexts.items():
            meta_obj = MorphFunctionMetaObject(
                id=value["id"] if "id" in value else None,
                name=value["name"] if "name" in value else None,
                function=value["function"] if "function" in value else None,
                description=value["description"] if "description" in value else None,
                title=value["title"] if "title" in value else None,
                variables=value["variables"] if "variables" in value else {},
                data_requirements=(
                    value["data_requirements"] if "data_requirements" in value else []
                ),
                connection=value["connection"] if "connection" in value else None,
            )
            self.update_meta_object(key, meta_obj)

        entirety_errors = self._check_entirety_errors()
        result.errors += entirety_errors
        self.__scans.append(result)
        return result.errors

    def partial_load(
        self, directory: str, target_name: str
    ) -> list[MorphFunctionLoadError]:
        """load required functions only, using cache.
        This function is meant to be used in runtime, where all the necessary analysis functions are already loaded
        except loading actual functions.
        """
        cwd = str(Path.cwd().resolve())
        if cwd not in sys.path:
            sys.path.append(cwd)

        cache = MorphFunctionMetaObjectCacheManager().get_cache()
        if cache is None:
            errors = self.load(directory)
            if len(errors) == 0:
                self.dump()

            return errors

        project = load_project(directory)
        if project is not None:
            source_paths = project.source_paths
        else:
            source_paths = []

        extra_paths: List[str] = []
        checksum_matched = True
        compare_dirs = []
        if len(source_paths) == 0:
            compare_dirs.append(Path(directory))
        else:
            for source_path in source_paths:
                compare_dirs.append(Path(f"{directory}/{source_path}"))

        for epath in extra_paths:
            epath_p = Path(epath)
            if not epath_p.exists() or not epath_p.is_dir():
                continue
            compare_dirs.append(epath_p)

        for compare_dir in compare_dirs:
            if cache.directory_checksums.get(
                compare_dir.as_posix(), ""
            ) != get_checksum(Path(compare_dir)):
                checksum_matched = False
                break

        if not checksum_matched:
            errors = self.load(directory)
            # NOTE: Do not return errors after a full load in order to avoid errors in unrelated files during execution.
            self.dump()
            if len(errors) < 1:
                return errors
            cache_ = MorphFunctionMetaObjectCacheManager().get_cache()
            if cache_ is not None:
                cache = cache_

        return self._partial_load(project, target_name, cache)

    def _partial_load(
        self,
        project: Optional[MorphProject],
        target_name: str,
        cache: MorphFunctionMetaObjectCache,
    ) -> list[MorphFunctionLoadError]:
        target_item: MorphFunctionMetaObjectCacheItem | None = None
        for item in cache.items:
            if item.spec.name == target_name or (
                item.spec.id and item.spec.id.startswith(target_name)
            ):
                target_item = item
                break
        for cache_error in cache.errors:
            if cache_error.name == target_name:
                return [cache_error]
        if target_item is None:
            return [
                MorphFunctionLoadError(
                    category=MorphFunctionLoadErrorCategory.IMPORT_ERROR,
                    file_path="",
                    name=target_name,
                    error="Alias not found",
                )
            ]

        suffix = target_item.file_path.split(".")[-1]
        if suffix == "py":
            for data_requirement in target_item.spec.data_requirements or []:
                for cache_error in cache.errors:
                    if cache_error.name == data_requirement:
                        return [cache_error]
                errors = self._partial_load(project, data_requirement, cache)
                if len(errors) > 0:
                    return errors
            _, error = _import_python_file(target_item.file_path)
        elif suffix == "sql":
            _, context, error = _import_sql_file(target_item.file_path)
            for key, value in context.items():
                meta = MorphFunctionMetaObject(
                    id=value["id"] if "id" in value else None,
                    name=value["name"] if "name" in value else None,
                    function=value["function"] if "function" in value else None,
                    description=(
                        value["description"] if "description" in value else None
                    ),
                    title=value["title"] if "title" in value else None,
                    variables=value["variables"] if "variables" in value else {},
                    data_requirements=(
                        value["data_requirements"]
                        if "data_requirements" in value
                        else []
                    ),
                    connection=value["connection"] if "connection" in value else None,
                )
                self.update_meta_object(key, meta)
                for data_requirement in target_item.spec.data_requirements or []:
                    for cache_error in cache.errors:
                        if cache_error.name == data_requirement:
                            return [cache_error]
                    errors = self._partial_load(project, data_requirement, cache)
                    if len(errors) > 0:
                        return errors
        else:
            return [
                MorphFunctionLoadError(
                    category=MorphFunctionLoadErrorCategory.IMPORT_ERROR,
                    file_path=target_item.file_path,
                    name=target_name,
                    error="Unknown file type",
                )
            ]

        errors = []
        if error is not None:
            errors.append(error)

        requirements = target_item.spec.data_requirements or []
        for requirement in requirements:
            errors += self._partial_load(project, requirement, cache)

        return errors

    def dump(self) -> MorphFunctionMetaObjectCache:
        if len(self.__scans) == 0:
            raise ValueError("No files are loaded.")

        scan = self.__scans[-1]
        cache_items: list[MorphFunctionMetaObjectCacheItem] = []
        for scan_item in scan.items:
            for obj in self.__meta_objects:
                # id is formatted as {filename}:{function_name}
                if sys.platform == "win32":
                    if len(obj.id.split(":")) > 2:
                        obj_filepath = obj.id.rsplit(":", 1)[0] if obj.id else ""
                    else:
                        obj_filepath = obj.id if obj.id else ""
                else:
                    obj_filepath = obj.id.split(":")[0] if obj.id else ""
                if scan_item.file_path == obj_filepath:
                    cache_obj = copy.deepcopy(obj)
                    if cache_obj.function:
                        cache_obj.function = None
                    item = MorphFunctionMetaObjectCacheItem(
                        spec=cache_obj,
                        file_path=scan_item.file_path,
                        checksum=scan_item.checksum,
                    )
                    cache_items.append(item)

        cache = MorphFunctionMetaObjectCache(
            directory=scan.directory,
            directory_checksums=scan.directory_checksums,
            items=cache_items,
            errors=scan.errors,
        )
        MorphFunctionMetaObjectCacheManager().set_cache(cache)

        return cache

    def _add_data(self, key: str, value: pd.DataFrame) -> None:
        self.__data[key] = value

    def _clear_var(self) -> None:
        self.__vars = {}

    def _add_var(self, key: str, value: Any) -> None:
        self.__vars[key] = value

    def update_meta_object(self, fid: str, obj: MorphFunctionMetaObject) -> None:
        MorphFunctionMetaObject.model_validate(obj)
        current_obj = self.search_meta_object(fid)
        if current_obj is None:
            obj.id = fid
            self.__meta_objects.append(obj)
        else:
            current_obj.id = obj.id
            current_obj.name = obj.name
            current_obj.function = obj.function or current_obj.function
            current_obj.description = obj.description or current_obj.description
            current_obje_variables = current_obj.variables or {}
            obj_variables = obj.variables or {}
            current_obj.variables = {**current_obje_variables, **obj_variables}
            current_obj.data_requirements = list(
                set(
                    (current_obj.data_requirements or [])
                    + (obj.data_requirements or [])
                )
            )
            current_obj.connection = obj.connection or current_obj.connection
            current_obj.title = obj.title or current_obj.title

    def search_meta_object(self, fid: str) -> MorphFunctionMetaObject | None:
        for obj in self.__meta_objects:
            if obj.id and obj.id == fid:
                return obj
        return None

    def search_meta_object_by_name(self, name: str) -> MorphFunctionMetaObject | None:
        for obj in self.__meta_objects:
            if obj.name and obj.name == name:
                return obj
        return None

    def search_meta_objects_by_path(
        self, file_path: str
    ) -> list[MorphFunctionMetaObject]:
        objects = []
        for obj in self.__meta_objects:
            if obj.id and obj.id.startswith(file_path):
                objects.append(obj)
        return objects

    def _check_entirety_errors(self) -> list[MorphFunctionLoadError]:
        # check is there's any missing or cyclic alias
        errors: list[MorphFunctionLoadError] = []
        names: list[str] = []
        ids: list[str] = []
        for obj in self.__meta_objects:
            if obj.name in names:
                obj_filepath = obj.id.split(":")[0] if obj.id else ""
                errors.append(
                    MorphFunctionLoadError(
                        category=MorphFunctionLoadErrorCategory.DUPLICATED_ALIAS,
                        file_path=obj_filepath,
                        name=obj.name,
                        error=f"Alias {obj.name} is also defined in {ids[names.index(obj.name)]}",
                    )
                )
                continue
            else:
                names.append(str(obj.name))
                ids.append(str(obj.id))

            requirements = obj.data_requirements or []
            for requirement in requirements:
                dependency = self.search_meta_object_by_name(requirement)
                if dependency is None:
                    obj_filepath = obj.id.split(":")[0] if obj.id else ""
                    errors.append(
                        MorphFunctionLoadError(
                            category=MorphFunctionLoadErrorCategory.MISSING_ALIAS,
                            file_path=obj_filepath,
                            name=requirement,
                            error=f"Requirement {requirement} is not found",
                        )
                    )
                elif obj.name in (dependency.data_requirements or []):
                    obj_filepath = obj.id.split(":")[0] if obj.id else ""
                    errors.append(
                        MorphFunctionLoadError(
                            category=MorphFunctionLoadErrorCategory.MISSING_ALIAS,
                            file_path=obj_filepath,
                            name=requirement,
                            error=f"Requirement {requirement} is cyclic",
                        )
                    )

        return errors

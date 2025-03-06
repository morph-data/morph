import importlib.util
import logging
import os
from pathlib import Path
from typing import Annotated, AsyncGenerator

import uvicorn
from colorama import Fore, Style
from fastapi import Depends, FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from inertia import (
    Inertia,
    InertiaConfig,
    InertiaResponse,
    InertiaVersionConflictException,
    inertia_dependency_factory,
    inertia_request_validation_exception_handler,
    inertia_version_conflict_exception_handler,
)
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from morph.api.error import ApiBaseError, InternalError, render_error_html
from morph.api.handler import router
from morph.api.plugin import plugin_app
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.state import (
    MorphFunctionMetaObjectCacheManager,
    MorphGlobalContext,
)

# configuration values

# logger
logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)

# set true to MORPH_LOCAL_DEV_MODE to use local frontend server
is_local_dev_mode = True if os.getenv("MORPH_LOCAL_DEV_MODE") == "true" else False


def custom_compile_logic():
    logger.info("Compiling python and sql files...")
    project_root = find_project_root_dir()
    context = MorphGlobalContext.get_instance()
    errors = context.load(project_root)
    if len(errors) > 0:
        error_message = "\n---\n".join(
            [
                f"{Fore.RED}{error.error.replace(chr(10), f'{Style.RESET_ALL}{chr(10)}{Fore.RED}')}{Style.RESET_ALL}"
                for error in errors
            ]
        )
        logger.error(
            f"""
{Fore.RED}Compilation failed.{Style.RESET_ALL}

{Fore.RED}Errors:{Style.RESET_ALL}
{error_message}
"""
        )
        response = HTMLResponse(
            content=render_error_html([error.error for error in errors]),
            status_code=500,
        )
        return response
    else:
        cache = MorphFunctionMetaObjectCacheManager().get_cache()
        if cache is not None and len(cache.items) > 0:
            api_description = f"""{Fore.MAGENTA}🚀 The endpoints generated are as follows.{Style.RESET_ALL}
{Fore.MAGENTA}You can access your Python functions and SQL over the APIs.

{Fore.MAGENTA}📕 Specification
{Fore.MAGENTA}[POST] /cli/run/{{alias}}/{{html,json}}
{Fore.MAGENTA}- Return the result as HTML or JSON. Please specify the types from "html", "json".
{Fore.MAGENTA}[POST] /cli/run-stream/{{alias}}
{Fore.MAGENTA}- Return the result as a stream. You need to use yield to return the result.
"""
            sql_api_description = ""
            python_api_description = ""
            for item in cache.items:
                if item.file_path.endswith(".sql"):
                    sql_api_description += (
                        f"{Fore.CYAN}- [POST] /cli/run/{item.spec.name}/{{json}}\n"
                    )
                else:
                    python_api_description += (
                        f"{Fore.CYAN}- [POST] /cli/run/{item.spec.name}/{{html,json}}\n"
                    )
                    python_api_description += (
                        f"{Fore.CYAN}- [POST] /cli/run-stream/{item.spec.name}\n"
                    )
            api_description += f"""
[SQL API]
{sql_api_description}
[Python API]
{python_api_description}"""
            logger.info(api_description)
        logger.info("🎉 Compilation completed.")
    return


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # startup event
    if os.environ.get("RUN_MAIN", "true") == "true" and is_local_dev_mode:
        error_response = custom_compile_logic()
        if error_response is not None:
            app.middleware_stack = error_response
            yield
            return
    yield
    # shutdown event
    logger.info("Shutting down...")


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="secret_key")
app.add_exception_handler(
    InertiaVersionConflictException,
    inertia_version_conflict_exception_handler,
)
app.add_exception_handler(
    RequestValidationError,
    inertia_request_validation_exception_handler,
)

frontend_dir = os.path.join(os.getcwd(), ".morph", "frontend")


def get_inertia_config():
    templates_dir = os.path.join(Path(__file__).resolve().parent, "templates")

    if is_local_dev_mode:
        front_port = os.getenv("MORPH_FRONT_PORT", "3000")
        frontend_url = f"http://localhost:{front_port}"
        templates = Jinja2Templates(directory=templates_dir)
        templates.env.globals["local_dev_mode"] = True
        templates.env.globals["frontend_url"] = frontend_url

        return InertiaConfig(
            templates=templates,
            environment="development",
            use_flash_messages=True,
            use_flash_errors=True,
            entrypoint_filename="main.tsx",
            assets_prefix="/src",
            dev_url=frontend_url,
        )

    return InertiaConfig(
        templates=Jinja2Templates(directory=templates_dir),
        manifest_json_path=os.path.join(frontend_dir, "dist", "manifest.json"),
        environment="production",
        entrypoint_filename="main.tsx",
    )


inertia_config = get_inertia_config()

InertiaDep = Annotated[Inertia, Depends(inertia_dependency_factory(inertia_config))]

if is_local_dev_mode:
    app.mount(
        "/src",
        StaticFiles(directory=os.path.join(frontend_dir, "src")),
        name="src",
    )
else:
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(frontend_dir, "dist", "assets")),
        name="assets",
    )

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.getcwd(), "static"), check_dir=False),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiBaseError)
async def handle_morph_error(_, exc):
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            }
        },
    )


@app.exception_handler(Exception)
async def handle_other_error(_, exc):
    exc = InternalError()
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            }
        },
    )


@app.get("/", response_model=None)
async def index(inertia: InertiaDep) -> InertiaResponse:
    return await inertia.render("index", {"showAdminPage": is_local_dev_mode})


@app.get(
    "/health",
)
async def health_check():
    return {"message": "ok"}


app.include_router(router)


def import_plugins():
    plugin_dir = Path(os.getcwd()) / "src/plugin"
    if plugin_dir.exists():
        for file in plugin_dir.glob("**/*.py"):
            if (
                file.stem.startswith("__") or file.stem.startswith(".")
            ) or file.is_dir():
                continue
            module_name = file.stem
            module_path = file.as_posix()
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception:  # noqa
                continue

    app.mount("/api/plugin", plugin_app)


import_plugins()


@app.get("/morph", response_model=None)
async def morph(inertia: InertiaDep) -> InertiaResponse:
    if is_local_dev_mode:
        return await inertia.render("morph", {"showAdminPage": True})

    return await inertia.render("404", {"showAdminPage": False})


@app.get("/{full_path:path}", response_model=None)
async def subpages(full_path: str, inertia: InertiaDep) -> InertiaResponse:
    return await inertia.render(full_path, {"showAdminPage": is_local_dev_mode})


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=False,
    )

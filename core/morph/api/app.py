import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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

from morph.api.cloud.utils import is_cloud
from morph.api.error import ApiBaseError, InternalError
from morph.api.handler import router
from morph.constants import MorphConstant

# configuration values
build_required = os.getenv("MORPH_FRONT_BUILD", "false")
host = os.getenv("MORPH_UVICORN_HOST", "0.0.0.0")
port = os.getenv("MORPH_UVICORN_PORT", "9002")
server_url = f"http://{host}:{port}"
front_url = "http://localhost:3000"
token = "dummy"
environment = "development"
entrypoint_filename = "main.tsx"
template_dir = os.path.join(Path(__file__).resolve().parent, "templates", "development")

if is_cloud():
    with open(MorphConstant.MORPH_CLOUD_CONFIG_PATH, "r") as f:
        domain = json.loads(f.read())["domain"]
        front_url = f"https://live2-{domain}"
        server_url = f"https://live-{domain}"
    with open(MorphConstant.MORPH_CLOUD_CONFIG_PATH, "r") as f:
        token = json.loads(f.read())["token"]

if build_required == "true":
    environment = "production"
    entrypoint_filename = "main-prod.tsx"
    template_dir = os.path.join(
        Path(__file__).resolve().parent, "templates", "production"
    )
else:
    init_index_template_path = os.path.join(
        Path(__file__).resolve().parent, "templates", "index.html"
    )
    with open(init_index_template_path, "r") as f:
        content = f.read()
        content = content.replace("FRONT_URL", front_url)
    index_template = os.path.join(template_dir, "index.html")
    with open(index_template, "w") as f:
        f.write(content)

templates = Jinja2Templates(directory=template_dir)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="secret_key")
app.add_exception_handler(
    InertiaVersionConflictException,
    inertia_version_conflict_exception_handler,
)
app.add_exception_handler(
    RequestValidationError,
    inertia_request_validation_exception_handler,
)

frontend_dir = os.path.join(Path(__file__).resolve().parents[1], "frontend")

manifest_json = os.path.join(frontend_dir, "dist", "manifest.json")
inertia_config = InertiaConfig(
    templates=templates,
    manifest_json_path=manifest_json,
    environment=environment,
    use_flash_messages=True,
    use_flash_errors=True,
    entrypoint_filename=entrypoint_filename,
    assets_prefix="/src",
    dev_url=front_url,
)
InertiaDep = Annotated[Inertia, Depends(inertia_dependency_factory(inertia_config))]

frontend_dir = (
    os.path.join(frontend_dir, "dist")
    if inertia_config.environment != "development"
    else os.path.join(frontend_dir, "src")
)

app.mount("/src", StaticFiles(directory=frontend_dir), name="src")
app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(frontend_dir, "assets")),
    name="assets",
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
    return await inertia.render(
        "index",
        {
            "baseUrl": server_url,
            "token": token,
        },
    )


@app.get(
    "/health",
)
async def health_check():
    return {"message": "ok"}


app.include_router(router)


@app.get("/{full_path:path}", response_model=None)
async def subpages(full_path: str, inertia: InertiaDep) -> InertiaResponse:
    cwd = os.getcwd()
    pages_dir = os.path.join(cwd, "src", "pages")
    if not os.path.exists(os.path.join(pages_dir, f"{full_path}.mdx")):
        return await inertia.render("404")

    return await inertia.render(
        full_path,
        {
            "baseUrl": server_url,
            "token": token,
        },
    )

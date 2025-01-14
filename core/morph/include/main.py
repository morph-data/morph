import os
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
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
from mangum import Mangum
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

template_dir = os.path.join(os.path.dirname(__file__), "templates")
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

manifest_json = os.path.join(
    os.path.dirname(__file__), "frontend", "dist", "manifest.json"
)
inertia_config = InertiaConfig(
    templates=templates,
    manifest_json_path=manifest_json,
    environment="production",
    use_flash_messages=True,
    use_flash_errors=True,
    entrypoint_filename="main.tsx",
    assets_prefix="/src",
    dev_url="http://localhost:3333",
)
InertiaDep = Annotated[Inertia, Depends(inertia_dependency_factory(inertia_config))]


frontend_dir = (
    os.path.join(os.path.dirname(__file__), "frontend", "dist")
    if inertia_config.environment != "development"
    else os.path.join(os.path.dirname(__file__), "frontend", "src")
)

app.mount("/src", StaticFiles(directory=frontend_dir), name="src")
app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(frontend_dir, "assets")),
    name="assets",
)


@app.get("/", response_model=None)
async def index(inertia: InertiaDep) -> InertiaResponse:
    return await inertia.render("index")


@app.get("/api/hello")
async def hello():
    return {"hello": "world"}


handler = Mangum(app)

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
from mangum import Mangum
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from morph.api.error import ApiBaseError, InternalError
from morph.api.handler import router

# configuration values

# set true to MORPH_LOCAL_DEV_MODE to use local frontend server
is_local_dev_mode = True if os.getenv("MORPH_LOCAL_DEV_MODE") == "true" else False

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


@app.get("/morph", response_model=None)
async def morph(inertia: InertiaDep) -> InertiaResponse:

    if is_local_dev_mode:
        return await inertia.render("morph", {"showAdminPage": True})

    return await inertia.render("404", {"showAdminPage": False})


@app.get("/{full_path:path}", response_model=None)
async def subpages(full_path: str, inertia: InertiaDep) -> InertiaResponse:
    return await inertia.render(full_path, {"showAdminPage": is_local_dev_mode})


handler = Mangum(app)

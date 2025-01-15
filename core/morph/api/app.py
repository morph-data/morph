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

from morph.api.error import ApiBaseError, InternalError
from morph.api.handler import router

# configuration values
environment = os.getenv("MORPH_ENV", "development")

template_dir = os.path.join(Path(__file__).resolve().parent, "templates")
templates = Jinja2Templates(directory=template_dir)

refresh_runtime_script = ""
if environment == "development":
    front_port = os.getenv("MORPH_FRONT_PORT", 3000)
    front_url = f"http://localhost:{front_port}"

    refresh_runtime_script = f"""
<script type="module">
import RefreshRuntime from "{front_url}/@react-refresh";
RefreshRuntime.injectIntoGlobalHook(window);
window.$RefreshReg$ = () => {{}};
window.$RefreshSig$ = () => (type) => type;
window.__vite_plugin_react_preamble_installed__ = true;
</script>
"""

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

manifest_json = os.path.join(frontend_dir, "dist", "manifest.json")
inertia_config = InertiaConfig(
    templates=templates,
    manifest_json_path=manifest_json,
    environment=environment,
    use_flash_messages=True,
    use_flash_errors=True,
    entrypoint_filename="main.tsx",
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
        "index", {"refresh_runtime_script": refresh_runtime_script}
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
        return await inertia.render(
            "404", {"refresh_runtime_script": refresh_runtime_script}
        )

    return await inertia.render(
        full_path, {"refresh_runtime_script": refresh_runtime_script}
    )

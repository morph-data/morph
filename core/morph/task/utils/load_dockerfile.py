from typing import Any, Dict, Optional, Tuple

import requests


def get_dockerfile_from_api(
    framework: str,
    provider: str,
    package_manager: Optional[str] = None,
    runtime: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Fetch dockerfile and dockerignore from the Morph API.

    Args:
        framework: The framework to get the dockerfile for
        provider: The provider to get the dockerfile for
        package_manager: Optional package manager to use
        runtime: Optional runtime to use

    Returns:
        Tuple containing (dockerfile, dockerignore)
    """
    url = f"https://dockerfile-template.morph-cb9.workers.dev/dockerfile/{framework}"

    params: Dict[str, Any] = {
        "provider": provider,
    }
    if package_manager:
        params["packageManager"] = package_manager
    if runtime:
        params["runtime"] = runtime

    response = requests.get(url, params=params)

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise ValueError(data["error"])

    return data["dockerfile"], data["dockerignore"]

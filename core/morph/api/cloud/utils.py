import os

from morph.constants import MorphConstant


def is_cloud() -> bool:
    cloud_path = MorphConstant.MORPH_DEPLOYMENT_PATH
    return os.path.exists(cloud_path)

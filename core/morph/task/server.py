import logging
import os

import click
import uvicorn


class UvicornLoggerHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        click.echo(log_entry, err=False)


logger = logging.getLogger("uvicorn")
logger.setLevel(logging.INFO)
handler = UvicornLoggerHandler()
formatter = logging.Formatter("%(levelname)s: %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


def start_server(host: str = "0.0.0.0", port: int = 9002) -> None:
    os.environ["MORPH_UVICORN_HOST"] = host
    os.environ["MORPH_UVICORN_PORT"] = str(port)

    uvicorn.run(
        "morph.api.app:app",
        host=host,
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    start_server()

import configparser
import os
import socket
import sys

import click

from morph.api.cloud.client import MorphApiClient, MorphApiKeyClientImpl
from morph.constants import MorphConstant
from morph.task.base import BaseTask


class ConfigTask(BaseTask):
    def run(self):
        profile_name = self.args.PROFILE or "default"

        # Verify network connectivity
        if not self.check_network_connection():
            click.echo("No network connection. Please check your internet settings.")
            return False

        # Check if the .morph directory exists in the user's home directory; create it if not
        morph_dir = MorphConstant.INIT_DIR
        if not os.path.exists(morph_dir):
            os.makedirs(morph_dir)
            click.echo(f"Created directory at {morph_dir}")

        # Request configuration settings from the user
        api_key = input("Please input your API Key on cloud: ")

        if not api_key:
            click.echo("Error: API key is required.")
            return False

        click.echo(click.style("Verifying the API Key..."))

        # set api key to environment variable
        os.environ["MORPH_API_KEY"] = api_key

        client = MorphApiClient(MorphApiKeyClientImpl)
        check_secret = client.req.check_api_secret()
        if check_secret.is_error():
            click.echo(
                click.style(
                    "Error: API key is invalid.",
                    fg="red",
                )
            )
            sys.exit(1)
        click.echo(click.style("✅ Verified", fg="green"))

        # Load existing file or create new one if it doesn't exist
        config = configparser.ConfigParser()
        cred_file = os.path.join(morph_dir, "credentials")
        if os.path.exists(cred_file):
            config.read(cred_file)

        # Warn user if profile already exists and prompt for overwrite
        if config.has_section(profile_name):
            warning_message = click.style(
                f"Warning: Profile '{profile_name}' already exists. Overwrite?",
                fg="yellow",
            )
            confirm = click.confirm(warning_message, default=False)
            if not confirm:
                click.echo(
                    click.style(
                        "Operation canceled. No credentials overwritten.",
                        fg="red",
                    )
                )
                sys.exit(1)
            click.echo("Overwriting existing credentials...")
        else:
            click.echo("Creating new credentials...")

        # Update the settings in the specific section
        config[profile_name] = {
            "api_key": api_key,
        }

        # Write the updated profile back to the file
        with open(cred_file, "w") as file:
            config.write(file)

        click.echo(f"Credentials saved to {cred_file}")
        click.echo(
            click.style(
                f"✅ Successfully setup! This profile can be accessed by profile name '{profile_name}' via morph cli.",
                fg="green",
            )
        )
        return True

    @staticmethod
    def check_network_connection():
        try:
            # Attempt to connect to Cloudflare DNS server on port 53
            socket.create_connection(("1.1.1.1", 53), timeout=10)
            return True
        except OSError:
            return False

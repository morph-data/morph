import configparser
import os
import socket

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
        team = client.req.find_team()
        if team.is_error():
            click.echo(
                click.style(
                    "Error: API key is invalid or does not have access to any team.",
                    fg="red",
                )
            )
            exit(1)
        click.echo(click.style("✅ Verified", fg="green"))

        click.echo(click.style("Please select workspace you want to use: "))

        workspace_response = client.req.list_workspaces()
        if workspace_response.is_error():
            click.echo(
                click.style("Error: Failed to retrieve workspaces list.", fg="red")
            )
            exit(1)
        workspaces = workspace_response.json()["items"]
        for i, workspace in enumerate(workspaces, start=1):
            workspace_name = workspace["databaseName"]
            click.echo(f"[{i}] {workspace_name}")

        selected_index = click.prompt("Enter the number of your choice", type=int)
        if 1 <= selected_index <= len(workspaces):
            selected_workspace = workspaces[selected_index - 1]["databaseName"]
            click.echo(f"You selected: {selected_workspace}")
        else:
            click.echo(click.style("Error: Invalid number selected.", fg="red"))
            exit(1)

        # Load existing file or create new one if it doesn't exist
        config = configparser.ConfigParser()
        cred_file = os.path.join(morph_dir, "credentials")
        if os.path.exists(cred_file):
            config.read(cred_file)

        # Update the settings in the specific section
        if not config.has_section(profile_name):
            click.echo("Creating new credentials...")
        else:
            click.echo("Credentials already exist. Updating...")
        config[profile_name] = {
            "workspace_id": workspaces[selected_index - 1]["databaseId"],
            "api_key": api_key,
        }

        # Write the updated profile back to the file
        with open(cred_file, "w") as file:
            config.write(file)

        click.echo(f"Credentials saved to {cred_file}")
        click.echo(
            click.style(
                f"✅ Successfully setup! This profile can be access by profile name '{profile_name}' via morph cli.",
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

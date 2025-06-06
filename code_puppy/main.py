import asyncio
import argparse
import os
from code_puppy.version_checker import fetch_latest_version
from code_puppy import __version__
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.console import ConsoleOptions, RenderResult
from rich.markdown import CodeBlock
from rich.text import Text
from rich.syntax import Syntax
from code_puppy.command_line.prompt_toolkit_completion import (
    get_input_with_path_completion,
)

# Initialize rich console for pretty output
from code_puppy.tools.common import console
from code_puppy.agent import code_generation_agent

from code_puppy.tools import *


# Define a function to get the secret file path
def get_secret_file_path():
    hidden_directory = os.path.join(os.path.expanduser("~"), ".agent_secret")
    if not os.path.exists(hidden_directory):
        os.makedirs(hidden_directory)
    return os.path.join(hidden_directory, "history.txt")


async def main():
    current_version = __version__
    latest_version = fetch_latest_version('code-puppy')
    console.print(f'Current version: {current_version}')
    console.print(f'Latest version: {latest_version}')
    if latest_version and latest_version != current_version:
        console.print(f'[bold yellow]A new version of code puppy is available: {latest_version}[/bold yellow]')
        console.print('[bold green]Please consider updating![/bold green]')
    global shutdown_flag
    shutdown_flag = False  # ensure this is initialized

    # Load environment variables from .env file
    load_dotenv()

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Code Puppy - A code generation agent")
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument("command", nargs="*", help="Run a single command")
    args = parser.parse_args()

    history_file_path = get_secret_file_path()

    if args.command:
        # Join the list of command arguments into a single string command
        command = " ".join(args.command)
        try:
            while not shutdown_flag:
                response = await code_generation_agent.run(command)
                agent_response = response.output
                console.print(agent_response.output_message)
                if agent_response.awaiting_user_input:
                    console.print(
                        "[bold red]The agent requires further input. Interactive mode is recommended for such tasks."
                    )
                break
        except AttributeError as e:
            console.print(f"[bold red]AttributeError:[/bold red] {str(e)}")
            console.print(
                "[bold yellow]\u26a0 The response might not be in the expected format, missing attributes like 'output_message'."
            )
        except Exception as e:
            console.print(f"[bold red]Unexpected Error:[/bold red] {str(e)}")
    elif args.interactive:
        await interactive_mode(history_file_path)
    else:
        parser.print_help()


# Add the file handling functionality for interactive mode
async def interactive_mode(history_file_path: str) -> None:
    """Run the agent in interactive mode."""
    console.print("[bold green]Code Puppy[/bold green] - Interactive Mode")
    console.print("Type 'exit' or 'quit' to exit the interactive mode.")
    console.print("Type 'clear' to reset the conversation history.")
    console.print(
        "Type [bold blue]@[/bold blue] followed by a path to use file path completion."
    )

    # Check if prompt_toolkit is installed
    try:
        import prompt_toolkit

        console.print("[dim]Using prompt_toolkit for enhanced tab completion[/dim]")
    except ImportError:
        console.print(
            "[yellow]Warning: prompt_toolkit not installed. Installing now...[/yellow]"
        )
        try:
            import subprocess

            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "prompt_toolkit"]
            )
            console.print("[green]Successfully installed prompt_toolkit[/green]")
        except Exception as e:
            console.print(f"[bold red]Error installing prompt_toolkit: {e}[/bold red]")
            console.print(
                "[yellow]Falling back to basic input without tab completion[/yellow]"
            )

    message_history = []

    # Set up history file in home directory
    history_file_path_prompt = os.path.expanduser("~/.code_puppy_history.txt")
    history_dir = os.path.dirname(history_file_path_prompt)

    # Ensure history directory exists
    if history_dir and not os.path.exists(history_dir):
        try:
            os.makedirs(history_dir, exist_ok=True)
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not create history directory: {e}[/yellow]"
            )

    while True:
        console.print("[bold blue]Enter your coding task:[/bold blue]")

        try:
            # Use prompt_toolkit for enhanced input with path completion
            try:
                # Use the async version of get_input_with_path_completion
                task = await get_input_with_path_completion(
                    ">>> 🐶 ", symbol="@", history_file=history_file_path_prompt
                )
            except ImportError:
                # Fall back to basic input if prompt_toolkit is not available
                task = input(">>> ")

        except (KeyboardInterrupt, EOFError):
            # Handle Ctrl+C or Ctrl+D
            console.print("\n[yellow]Input cancelled[/yellow]")
            continue

        # Check for exit commands
        if task.strip().lower() in ["exit", "quit"]:
            console.print("[bold green]Goodbye![/bold green]")
            break

        # Check for clear command
        if task.strip().lower() == "clear":
            message_history = []
            console.print("[bold yellow]Conversation history cleared![/bold yellow]")
            console.print(
                "[dim]The agent will not remember previous interactions.[/dim]\n"
            )
            continue

        if task.strip():
            console.print(f"\n[bold blue]Processing task:[/bold blue] {task}\n")

            # Write to the secret file for permanent history
            with open(history_file_path, "a") as f:
                f.write(f"{task}\n")

            try:
                prettier_code_blocks()

                console.log(f"Asking: {task}...", style="cyan")

                # Store agent's full response
                agent_response = None

                result = await code_generation_agent.run(
                    task, message_history=message_history
                )
                # Get the structured response
                agent_response = result.output
                console.print(agent_response.output_message)

                # Update message history with all messages from this interaction
                message_history = result.new_messages()

                if agent_response and agent_response.awaiting_user_input:
                    console.print(
                        "\n[bold yellow]\u26a0 Agent needs your input to continue.[/bold yellow]"
                    )

                # Show context status
                console.print(
                    f"[dim]Context: {len(message_history)} messages in history[/dim]\n"
                )

            except Exception:
                console.print_exception(show_locals=True)


def prettier_code_blocks():
    class SimpleCodeBlock(CodeBlock):
        def __rich_console__(
            self, console: Console, options: ConsoleOptions
        ) -> RenderResult:
            code = str(self.text).rstrip()
            yield Text(self.lexer_name, style="dim")
            syntax = Syntax(
                code,
                self.lexer_name,
                theme=self.theme,
                background_color="default",
                line_numbers=True,
            )
            yield syntax
            yield Text(f"/{self.lexer_name}", style="dim")

    Markdown.elements["fence"] = SimpleCodeBlock


def main_entry():
    """Entry point for the installed CLI tool."""
    asyncio.run(main())


if __name__ == "__main__":
    main_entry()

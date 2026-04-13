"""
consumed-ai CLI — local daemon, environment scanner, channel connector.

Phase 8 of consumed.ai activation plan. Thin client that bridges to
consumed.ai cloud intelligence while running a local daemon for speed.

Usage:
    consumed-ai start              # Start local daemon
    consumed-ai scan               # Scan environment
    consumed-ai connect telegram   # Connect a channel
    consumed-ai status             # Check daemon & bridge status
    consumed-ai chat               # Interactive chat in terminal
    consumed-ai key store openai   # Store an LLM API key
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

import click

from consumed_ai import __version__


def _get_data_dir() -> Path:
    """Get the consumed-ai data directory."""
    data_dir = Path(os.environ.get("CONSUMED_AI_DATA_DIR", Path.home() / ".consumed-ai"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@click.group()
@click.version_option(__version__, prog_name="consumed-ai")
def main():
    """consumed.ai — Execute any software via natural language."""
    pass


@main.command()
@click.option("--port", default=9190, help="Daemon port (default: 9190)")
@click.option("--cloud-url", default="https://api.consumed.ai", help="Cloud API URL")
@click.option("--no-cloud", is_flag=True, help="Run in offline-only mode")
def start(port: int, cloud_url: str, no_cloud: bool):
    """Start the consumed-ai local daemon."""
    from rich.console import Console
    console = Console()

    console.print(f"[bold]consumed.ai[/bold] v{__version__}")
    console.print(f"  Data: {_get_data_dir()}")
    console.print(f"  Port: {port}")
    console.print(f"  Cloud: {'disabled' if no_cloud else cloud_url}")

    from consumed_ai.daemon_lite import run_daemon
    asyncio.run(run_daemon(
        port=port,
        data_dir=str(_get_data_dir()),
        cloud_url=None if no_cloud else cloud_url,
    ))


@main.command()
@click.option("--include-packages", is_flag=True, default=True, help="Scan pip/npm packages")
@click.option("--include-docker", is_flag=True, default=True, help="Scan Docker containers")
@click.option("--json-output", is_flag=True, help="Output as JSON")
def scan(include_packages: bool, include_docker: bool, json_output: bool):
    """Scan your environment for installed tools, packages, and services."""
    from rich.console import Console
    from rich.table import Table
    from consumed_ai.scanner import scan_environment

    results = scan_environment(
        include_packages=include_packages,
        include_docker=include_docker,
    )

    if json_output:
        click.echo(json.dumps(results, indent=2, default=str))
        return

    console = Console()
    console.print("\n[bold]Environment Scan Results[/bold]\n")

    # CLI tools
    if results.get("cli_tools"):
        table = Table(title="CLI Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Version")
        table.add_column("Service", style="green")
        for t in results["cli_tools"]:
            table.add_row(t["tool"], t.get("version", ""), t["service"])
        console.print(table)

    # Python packages
    if results.get("python_packages"):
        table = Table(title="Python Packages (API-relevant)")
        table.add_column("Package", style="cyan")
        table.add_column("Version")
        for p in results["python_packages"][:20]:
            table.add_row(p["package"], p.get("version", ""))
        console.print(table)

    # Env credentials
    if results.get("env_credentials"):
        table = Table(title="Detected Credentials", style="yellow")
        table.add_column("Variable", style="yellow")
        table.add_column("Service", style="green")
        for c in results["env_credentials"]:
            table.add_row(c["env_var"], c["service"])
        console.print(table)

    # Docker
    if results.get("docker_containers"):
        table = Table(title="Docker Containers")
        table.add_column("Name", style="cyan")
        table.add_column("Image")
        table.add_column("Status", style="green")
        for c in results["docker_containers"]:
            table.add_row(c["name"], c["image"], c.get("status", ""))
        console.print(table)

    console.print(f"\n[bold]Total:[/bold] {len(results.get('services_detected', []))} services detected")


@main.command()
@click.argument("channel_type", type=click.Choice(["telegram", "slack", "discord", "webchat"]))
@click.option("--token", prompt=True, hide_input=True, help="Bot token for the channel")
def connect(channel_type: str, token: str):
    """Connect a messaging channel."""
    from rich.console import Console
    console = Console()

    config_path = _get_data_dir() / "config.yaml"
    config = {}
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

    config.setdefault("channels", {})
    config["channels"][channel_type] = {"token": token, "enabled": True}

    import yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    console.print(f"[green]Connected {channel_type}[/green] — restart daemon to activate")


@main.command()
def status():
    """Check daemon and bridge status."""
    from rich.console import Console
    console = Console()

    try:
        import httpx
        resp = httpx.get("http://localhost:9190/api/health", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            console.print("[green]Daemon running[/green]")
            console.print(f"  Uptime: {data.get('uptime_seconds', 0)}s")
            console.print(f"  Channels: {data.get('channels_connected', 0)}")
            console.print(f"  Bridge: {'connected' if data.get('bridge_connected') else 'disconnected'}")
        else:
            console.print("[red]Daemon unhealthy[/red]")
    except Exception:
        console.print("[yellow]Daemon not running[/yellow] — use `consumed-ai start`")


@main.command()
def chat():
    """Interactive chat in the terminal."""
    from rich.console import Console
    console = Console()
    console.print("[bold]consumed.ai chat[/bold] — type 'quit' to exit\n")

    while True:
        try:
            query = console.input("[cyan]> [/cyan]")
        except (EOFError, KeyboardInterrupt):
            break

        if query.strip().lower() in ("quit", "exit", "q"):
            break

        if not query.strip():
            continue

        try:
            import httpx
            resp = httpx.post(
                "http://localhost:9190/api/execute",
                json={"shortcode": query},
                timeout=30,
            )
            data = resp.json()
            if data.get("success"):
                result = data.get("data", data.get("result", ""))
                if isinstance(result, dict):
                    console.print_json(json.dumps(result, default=str))
                else:
                    console.print(str(result))
            else:
                console.print(f"[red]Error:[/red] {data.get('error', 'Unknown error')}")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print("[yellow]Is the daemon running? Use `consumed-ai start`[/yellow]")


@main.group()
def key():
    """Manage LLM API keys (BYOK)."""
    pass


@key.command("store")
@click.argument("provider", type=click.Choice(["anthropic", "openai", "groq", "google"]))
@click.option("--api-key", prompt=True, hide_input=True, help="Your API key")
def key_store(provider: str, api_key: str):
    """Store an LLM API key for BYOK."""
    from consumed_ai.vault_local import LocalVault

    vault = LocalVault(data_dir=str(_get_data_dir()))
    vault.store(f"{provider}_api_key", api_key)

    from rich.console import Console
    Console().print(f"[green]Stored {provider} key[/green] (encrypted locally)")


@key.command("list")
def key_list():
    """List stored LLM keys."""
    from consumed_ai.vault_local import LocalVault
    from rich.console import Console

    vault = LocalVault(data_dir=str(_get_data_dir()))
    console = Console()

    for provider in ["anthropic", "openai", "groq", "google"]:
        key_name = f"{provider}_api_key"
        stored = vault.get(key_name) is not None
        status = "[green]stored[/green]" if stored else "[dim]not set[/dim]"
        console.print(f"  {provider}: {status}")


if __name__ == "__main__":
    main()

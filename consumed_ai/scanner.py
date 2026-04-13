"""
Environment scanner — extracted from consumed-bot's onboarding/scanner.py.

Phase 8: standalone scanner for the pip-installable package.
Detects CLI tools, Python/Node packages, env var credentials, Docker containers.
"""

import json
import logging
import os
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

CLI_TOOLS = {
    "stripe": "stripe", "gh": "github", "gcloud": "google_cloud",
    "aws": "aws", "heroku": "heroku", "vercel": "vercel",
    "netlify": "netlify", "fly": "fly_io", "railway": "railway",
    "supabase": "supabase", "firebase": "firebase", "docker": "docker",
    "kubectl": "kubernetes", "terraform": "terraform", "twilio": "twilio",
    "ngrok": "ngrok", "node": "nodejs", "python3": "python",
    "redis-cli": "redis", "psql": "postgresql", "mongosh": "mongodb",
}

API_PACKAGES = {
    "stripe", "twilio", "sendgrid", "boto3", "google-api-python-client",
    "slack-sdk", "discord.py", "openai", "anthropic", "groq", "httpx",
    "flask", "fastapi", "django", "redis", "pymongo", "psycopg2",
    "supabase", "firebase-admin", "langchain", "llama-index",
    "transformers", "torch", "tensorflow", "pandas", "docker",
}

ENV_KEY_PATTERNS = {
    "STRIPE_SECRET_KEY": "stripe", "OPENAI_API_KEY": "openai",
    "ANTHROPIC_API_KEY": "anthropic", "GROQ_API_KEY": "groq",
    "GITHUB_TOKEN": "github", "AWS_ACCESS_KEY_ID": "aws",
    "SLACK_BOT_TOKEN": "slack", "DISCORD_BOT_TOKEN": "discord",
    "TWILIO_AUTH_TOKEN": "twilio", "SENDGRID_API_KEY": "sendgrid",
    "DATABASE_URL": "database", "REDIS_URL": "redis",
}


def scan_environment(
    include_packages: bool = True,
    include_docker: bool = True,
) -> Dict[str, Any]:
    """Run all scans and return combined results."""
    cli_tools = _scan_cli_tools()
    config_files = _scan_config_files()
    running = _scan_running_services()
    env_creds = _scan_env_credentials()

    result = {
        "cli_tools": cli_tools,
        "config_files": config_files,
        "running_services": running,
        "env_credentials": env_creds,
        "services_detected": list(set(
            [t["service"] for t in cli_tools] +
            [c["service"] for c in config_files] +
            [r["service"] for r in running] +
            [c["service"] for c in env_creds]
        )),
    }

    if include_packages:
        result["python_packages"] = _scan_python_packages()
        result["node_packages"] = _scan_node_packages()
        result["services_detected"] = list(set(
            result["services_detected"] +
            [p["service"] for p in result["python_packages"]] +
            [p["service"] for p in result["node_packages"]]
        ))

    if include_docker:
        result["docker_containers"] = _scan_docker_containers()
        result["services_detected"] = list(set(
            result["services_detected"] +
            [c["service"] for c in result.get("docker_containers", [])]
        ))

    return result


def _scan_cli_tools() -> List[Dict[str, Any]]:
    found = []
    for tool, service in CLI_TOOLS.items():
        path = shutil.which(tool)
        if path:
            found.append({"tool": tool, "path": path, "service": service})
    return found


def _scan_config_files() -> List[Dict[str, Any]]:
    home = Path.home()
    checks = {
        ".aws/credentials": "aws", ".kube/config": "kubernetes",
        ".docker/config.json": "docker", ".gitconfig": "github",
        ".stripe/config.toml": "stripe", ".config/gh/hosts.yml": "github",
    }
    return [
        {"file": p, "service": s}
        for p, s in checks.items()
        if (home / p).exists()
    ]


def _scan_running_services() -> List[Dict[str, Any]]:
    ports = {5432: "postgresql", 3306: "mysql", 27017: "mongodb",
             6379: "redis", 9200: "elasticsearch", 8080: "http_server"}
    found = []
    for port, service in ports.items():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    found.append({"port": port, "service": service})
        except Exception:
            pass
    return found


def _scan_python_packages() -> List[Dict[str, Any]]:
    try:
        result = subprocess.run(
            ["pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return [
                {"package": p["name"], "version": p.get("version", ""),
                 "service": p["name"].lower().replace("-", "_")}
                for p in packages
                if p["name"].lower() in API_PACKAGES
            ]
    except Exception:
        pass
    return []


def _scan_node_packages() -> List[Dict[str, Any]]:
    try:
        result = subprocess.run(
            ["npm", "list", "-g", "--json", "--depth=0"],
            capture_output=True, text=True, timeout=15,
        )
        if result.stdout:
            data = json.loads(result.stdout)
            return [
                {"package": name, "version": info.get("version", ""),
                 "service": name.replace("-", "_")}
                for name, info in data.get("dependencies", {}).items()
            ]
    except Exception:
        pass
    return []


def _scan_env_credentials() -> List[Dict[str, Any]]:
    found = []
    seen = set()
    for env_name, service in ENV_KEY_PATTERNS.items():
        value = os.environ.get(env_name, "")
        if value and len(value) > 8 and service not in seen:
            seen.add(service)
            found.append({"env_var": env_name, "service": service, "key_length": len(value)})
    return found


def _scan_docker_containers() -> List[Dict[str, Any]]:
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            found = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    found.append({
                        "name": parts[0], "image": parts[1],
                        "status": parts[2] if len(parts) > 2 else "",
                        "service": parts[1].split(":")[0].split("/")[-1],
                    })
            return found
    except Exception:
        pass
    return []

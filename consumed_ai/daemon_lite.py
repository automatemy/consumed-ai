"""
Lightweight daemon — local FastAPI server for the pip-installable package.

Phase 8: runs locally without Docker. Provides grammar parsing, execution
via cloud bridge, and channel connectors. Minimal footprint compared to
the full consumed-bot daemon.

Architecture:
  Local: grammar parsing, credential vault, channel connectors
  Cloud: execution, intelligence, agent system (via bridge)
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExecuteRequest(BaseModel):
    shortcode: str
    user_id: str = "local"


async def run_daemon(
    port: int = 9190,
    data_dir: str = "",
    cloud_url: Optional[str] = "https://api.consumed.ai",
):
    """Start the lightweight local daemon."""
    import uvicorn

    if not data_dir:
        data_dir = str(Path.home() / ".consumed-ai")

    app = create_app(data_dir=data_dir, cloud_url=cloud_url)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)

    logger.info(f"consumed-ai daemon starting on port {port}")
    await server.serve()


def create_app(
    data_dir: str = "",
    cloud_url: Optional[str] = None,
) -> FastAPI:
    """Create the lightweight FastAPI app."""
    app = FastAPI(
        title="consumed-ai",
        version="0.1.0",
        docs_url="/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # State
    app.state.data_dir = data_dir
    app.state.cloud_url = cloud_url
    app.state.start_time = time.time()
    app.state.cloud_connected = False

    # Initialize local vault
    from consumed_ai.vault_local import LocalVault
    app.state.vault = LocalVault(data_dir=data_dir)

    # Initialize local grammar cache
    grammar_dir = Path(data_dir) / "grammars"
    grammar_dir.mkdir(parents=True, exist_ok=True)
    app.state.grammar_dir = grammar_dir

    # Try cloud connection
    @app.on_event("startup")
    async def startup():
        if cloud_url:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{cloud_url}/health")
                    app.state.cloud_connected = resp.status_code == 200
                    if app.state.cloud_connected:
                        logger.info(f"Cloud bridge connected: {cloud_url}")
            except Exception:
                logger.info("Cloud bridge unavailable — running in offline mode")

    # Routes
    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "version": "0.1.0",
            "uptime_seconds": int(time.time() - app.state.start_time),
            "cloud_connected": app.state.cloud_connected,
            "credentials_stored": app.state.vault.count,
        }

    @app.post("/api/execute")
    async def execute(body: ExecuteRequest):
        """Execute a shortcode — try local grammar first, fall back to cloud."""
        shortcode = body.shortcode.strip()
        if not shortcode:
            raise HTTPException(400, "Empty shortcode")

        # Try cloud execution
        if app.state.cloud_url and app.state.cloud_connected:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{app.state.cloud_url}/api/execute",
                        json={"shortcode": shortcode, "user_id": body.user_id},
                    )
                    if resp.status_code == 200:
                        return resp.json()
            except Exception as e:
                logger.warning(f"Cloud execution failed: {e}")

        return {"success": False, "error": "Cloud bridge unavailable and no local grammar match"}

    @app.get("/api/scan")
    async def scan():
        """Run environment scan."""
        from consumed_ai.scanner import scan_environment
        return scan_environment()

    @app.get("/api/credentials")
    async def list_credentials():
        """List stored credential keys."""
        return {"keys": app.state.vault.list_keys(), "count": app.state.vault.count}

    @app.post("/api/credentials")
    async def store_credential(body: dict):
        """Store a credential."""
        key = body.get("key", "")
        value = body.get("value", "")
        if not key or not value:
            raise HTTPException(400, "key and value required")
        app.state.vault.store(key, value)
        return {"success": True, "key": key}

    @app.get("/api/model-tiers")
    async def model_tiers():
        """Get BYOK model tier recommendations."""
        return {
            "tiers": {
                "fast_cheap": {
                    "description": "Fast and cheap — high-volume automation",
                    "models": ["groq/llama-3.3-70b", "claude-haiku", "gemini-flash"],
                },
                "balanced": {
                    "description": "Balanced — multi-service reasoning",
                    "models": ["claude-sonnet", "gpt-4o-mini", "gemini-pro"],
                },
                "maximum": {
                    "description": "Maximum intelligence — complex planning",
                    "models": ["claude-opus", "gpt-4o", "gemini-ultra"],
                },
                "coding": {
                    "description": "Coding specialist — development tasks",
                    "models": ["claude-sonnet", "gpt-4o", "deepseek-coder"],
                },
            }
        }

    return app

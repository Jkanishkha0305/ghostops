"""
DigitalOcean Gradient AI Platform integration — agent management, knowledge bases, guardrails.

This module manages GhostOps agents on the DO Gradient AI Platform:
- Registers specialist agents (router, vision, CLI, screen)
- Creates and manages knowledge bases for RAG
- Attaches guardrails for safety

Requires: DIGITAL_OCEAN_KEY (API token) in .env
"""
import os
from typing import Optional

import httpx

DO_API_BASE = "https://api.digitalocean.com/v2"
DO_GENAI_BASE = f"{DO_API_BASE}/gen-ai"

# Agent definitions for GhostOps
GHOSTOPS_AGENTS = {
    "router": {
        "name": "ghostops-router",
        "model_id": "llama3.3-70b-instruct",
        "model_uuid": "d754f2d7-d1f0-11ef-bf8f-4e013e2ddde4",
        "instruction": (
            "You are a desktop assistant router for GhostOps. "
            "Given a user request, classify intent and delegate to the correct specialist agent:\n"
            "- ghostops-vision: GUI interactions (click, type, scroll)\n"
            "- ghostops-cli: shell commands, open apps, file ops\n"
            "- ghostops-screen: explain/annotate what's on screen\n"
            "- direct: answer questions without computer actions\n"
            "Return JSON: {\"agent\": \"<name>\", \"task\": \"<task>\", \"response_text\": \"<if direct>\"}"
        ),
        "description": "Multi-agent router that classifies user intent and delegates to specialist desktop agents",
        "tags": ["ghostops", "router"],
    },
    "vision": {
        "name": "ghostops-vision",
        "model_id": "openai-gpt-4o",
        "model_uuid": "9a364867-f300-11ef-bf8f-4e013e2ddde4",
        "instruction": (
            "You are a vision-based desktop control agent. You analyze screenshots and issue "
            "precise tool calls (go_to_element, click, type_string, press_hotkey) to interact "
            "with GUI elements. Always verify actions via screenshot before proceeding. "
            "Use open_application for launching apps instead of Spotlight."
        ),
        "description": "Computer use agent with screen vision for mouse and keyboard automation",
        "tags": ["ghostops", "vision", "computer-use"],
    },
    "cli": {
        "name": "ghostops-cli",
        "model_id": "llama3.3-70b-instruct",
        "model_uuid": "d754f2d7-d1f0-11ef-bf8f-4e013e2ddde4",
        "instruction": (
            "You are a macOS shell command generator. Given a task, output ONLY the safe shell "
            "command to run. Use `open -a` for apps, standard Unix for file ops. "
            "Never output dangerous commands (rm -rf /, mkfs, dd). If unsafe, output CANNOT_EXECUTE."
        ),
        "description": "Safe shell command generation and execution agent for macOS",
        "tags": ["ghostops", "cli", "shell"],
    },
    "screen": {
        "name": "ghostops-screen",
        "model_id": "openai-gpt-4o",
        "model_uuid": "9a364867-f300-11ef-bf8f-4e013e2ddde4",
        "instruction": (
            "You are a screen annotation agent. You analyze screenshots and draw bounding boxes, "
            "labels, and text annotations to visually explain what is on screen. "
            "Use draw_bounding_box, draw_point, and create_text tools to annotate elements."
        ),
        "description": "Visual screen annotation agent that explains UI elements with overlay graphics",
        "tags": ["ghostops", "screen", "annotation"],
    },
}

# Embedding model for knowledge bases
EMBEDDING_MODEL_UUID = "22653204-79ed-11ef-bf8f-4e013e2ddde4"  # GTE Large EN v1.5


def _headers() -> dict:
    token = os.environ.get("DIGITAL_OCEAN_KEY", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _get_project_id() -> str:
    """Get default project ID."""
    return os.environ.get("DO_PROJECT_ID", "54701170-33b9-445c-9d33-029ec6be0324")


# ── Agent Management ──────────────────────────────────────────────────────────

async def create_agent(
    name: str,
    model_uuid: str,
    instruction: str,
    description: str = "",
    tags: Optional[list[str]] = None,
    region: str = "tor1",
    knowledge_base_uuids: Optional[list[str]] = None,
) -> dict:
    """Create an agent on the DO Gradient AI Platform."""
    payload = {
        "name": name,
        "model_uuid": model_uuid,
        "instruction": instruction,
        "description": description,
        "project_id": _get_project_id(),
        "region": region,
    }
    if tags:
        payload["tags"] = tags
    if knowledge_base_uuids:
        payload["knowledge_base_uuid"] = knowledge_base_uuids

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DO_GENAI_BASE}/agents",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        return resp.json()


async def list_agents() -> list[dict]:
    """List all agents on the DO platform."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DO_GENAI_BASE}/agents",
            headers=_headers(),
            timeout=30,
        )
        data = resp.json()
        return data.get("agents", [])


async def register_all_ghostops_agents() -> dict[str, dict]:
    """Register all GhostOps specialist agents on DO. Returns {role: response}."""
    results = {}
    for role, config in GHOSTOPS_AGENTS.items():
        print(f"[DO Platform] Creating agent: {config['name']}...")
        result = await create_agent(
            name=config["name"],
            model_uuid=config["model_uuid"],
            instruction=config["instruction"],
            description=config["description"],
            tags=config.get("tags"),
        )
        results[role] = result
        if "id" in str(result):
            print(f"[DO Platform] Created {config['name']}: {result}")
        else:
            print(f"[DO Platform] Warning creating {config['name']}: {result}")
    return results


# ── Knowledge Base ────────────────────────────────────────────────────────────

async def create_knowledge_base(
    name: str,
    region: str = "tor1",
    datasource_urls: Optional[list[str]] = None,
) -> dict:
    """Create a knowledge base on the DO platform."""
    # Knowledge bases require at least one datasource
    datasources = []
    if datasource_urls:
        for url in datasource_urls:
            datasources.append({"type": "WebCrawler", "url": url})
    else:
        # Default: crawl the GhostOps GitHub README as a datasource
        datasources.append({
            "type": "WebCrawler",
            "url": "https://github.com/jkanishkha0305/ghostops",
        })

    payload = {
        "name": name,
        "embedding_model_uuid": EMBEDDING_MODEL_UUID,
        "project_id": _get_project_id(),
        "region": region,
        "datasources": datasources,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DO_GENAI_BASE}/knowledge_bases",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        return resp.json()


async def list_knowledge_bases() -> list[dict]:
    """List all knowledge bases."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DO_GENAI_BASE}/knowledge_bases",
            headers=_headers(),
            timeout=30,
        )
        data = resp.json()
        return data.get("knowledge_bases", [])


# ── Guardrails ────────────────────────────────────────────────────────────────

async def create_guardrail(
    name: str,
    guardrail_type: str = "GUARDRAIL_TYPE_JAILBREAK",
    description: str = "",
    default_response: str = "I cannot fulfill this request for safety reasons.",
    **_kwargs,
) -> dict:
    """Create a guardrail on the DO platform."""
    payload = {
        "name": name,
        "guardrail_type": guardrail_type,
        "description": description,
        "default_response": default_response,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DO_GENAI_BASE}/guardrails",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        return resp.json()


async def setup_ghostops_guardrails() -> list[dict]:
    """Create safety guardrails for GhostOps agents."""
    guardrails = [
        {
            "name": "ghostops-jailbreak-protection",
            "type": "GUARDRAIL_TYPE_JAILBREAK",
            "description": "Prevents prompt injection and jailbreak attempts on desktop agent",
            "default_response": "I cannot execute that action for safety reasons.",
        },
        {
            "name": "ghostops-content-moderation",
            "type": "GUARDRAIL_TYPE_CONTENT_MODERATION",
            "description": "Filters inappropriate content from agent responses",
            "default_response": "I cannot generate that type of content.",
        },
        {
            "name": "ghostops-sensitive-data",
            "type": "GUARDRAIL_TYPE_SENSITIVE_DATA",
            "description": "Prevents leaking API keys, passwords, or PII seen on screen",
            "default_response": "I detected sensitive information and will not include it in my response.",
        },
    ]
    results = []
    for g in guardrails:
        print(f"[DO Platform] Creating guardrail: {g['name']}...")
        result = await create_guardrail(**g)
        results.append(result)
        print(f"[DO Platform] Result: {result}")
    return results


# ── Setup All ─────────────────────────────────────────────────────────────────

async def setup_do_platform():
    """One-shot setup: create agents, knowledge base, guardrails on DO."""
    print("=" * 60)
    print("[DO Platform] Setting up GhostOps on DigitalOcean Gradient AI")
    print("=" * 60)

    # 1. Register agents
    print("\n--- Creating Agents ---")
    agents = await register_all_ghostops_agents()

    # 2. Create knowledge base
    print("\n--- Creating Knowledge Base ---")
    kb = await create_knowledge_base("ghostops-workflows")
    print(f"[DO Platform] Knowledge Base: {kb}")

    # 3. Create guardrails
    print("\n--- Creating Guardrails ---")
    guardrails = await setup_ghostops_guardrails()

    print("\n" + "=" * 60)
    print("[DO Platform] Setup complete!")
    print("=" * 60)

    return {
        "agents": agents,
        "knowledge_base": kb,
        "guardrails": guardrails,
    }


# CLI entry point
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(setup_do_platform())

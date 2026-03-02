"""Shared configuration loader for the demo scripts."""

import os
import sys

from dotenv import load_dotenv


def load_config() -> dict:
    """Load configuration from .env file and return as a dictionary."""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.exists(env_path):
        print("[red]Error:[/red] .env file not found. Run 01_deploy_infra.ps1 first.")
        sys.exit(1)

    load_dotenv(env_path, override=True)

    required_vars = [
        "AZURE_SEARCH_ENDPOINT",
        "PROJECT_ENDPOINT",
        "PROJECT_RESOURCE_ID",
        "AZURE_OPENAI_ENDPOINT",
    ]

    config = {}
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        config[var] = value

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("Please check your .env file.")
        sys.exit(1)

    # Optional vars with defaults
    config["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"] = os.getenv(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"
    )
    config["AZURE_OPENAI_EMBEDDING_MODEL"] = os.getenv(
        "AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"
    )
    config["AZURE_OPENAI_GPT_DEPLOYMENT"] = os.getenv(
        "AZURE_OPENAI_GPT_DEPLOYMENT", "gpt-4o"
    )
    config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"] = os.getenv(
        "AZURE_OPENAI_GPT_MINI_DEPLOYMENT", "gpt-4o-mini"
    )
    config["AZURE_STORAGE_CONNECTION_STRING"] = os.getenv(
        "AZURE_STORAGE_CONNECTION_STRING", ""
    )
    config["AZURE_STORAGE_CONTAINER_NAME"] = os.getenv(
        "AZURE_STORAGE_CONTAINER_NAME", "documents"
    )
    config["AZURE_AI_SERVICES_ENDPOINT"] = os.getenv(
        "AZURE_AI_SERVICES_ENDPOINT", ""
    )
    # Foundry project (CognitiveServices-based, for agent + MCP)
    config["FOUNDRY_PROJECT_ENDPOINT"] = os.getenv(
        "FOUNDRY_PROJECT_ENDPOINT", ""
    )
    config["FOUNDRY_PROJECT_RESOURCE_ID"] = os.getenv(
        "FOUNDRY_PROJECT_RESOURCE_ID", ""
    )
    config["AGENT_MODEL"] = os.getenv("AGENT_MODEL", "gpt-4o")
    config["KNOWLEDGE_SOURCE_NAME"] = os.getenv(
        "KNOWLEDGE_SOURCE_NAME", "demo-blob-ks"
    )
    config["KNOWLEDGE_BASE_NAME"] = os.getenv(
        "KNOWLEDGE_BASE_NAME", "demo-knowledge-base"
    )
    config["AZURE_SEARCH_API_KEY"] = os.getenv(
        "AZURE_SEARCH_API_KEY", ""
    )

    return config

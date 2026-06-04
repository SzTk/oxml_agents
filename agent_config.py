import argparse
import os
import warnings
from pathlib import Path

# Suppress known warnings from any_agent / any_llm / asyncio internals
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=ResourceWarning)


def _load_dotenv(env_path: str = ".env") -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = value


def get_agent_args(default_prompt: str = "") -> tuple[str, str, str, str]:
    """Return (model_id, api_base, api_key, prompt) from .env / env vars / CLI args.

    Priority: CLI args > environment variables > .env file > built-in defaults.

    CLI usage:
        python agent_foo.py [PROMPT] [--model MODEL_ID] [--api-base URL] [--port PORT] [--api-key KEY]
    """
    _load_dotenv()

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("prompt", nargs="?", default=None, help="Prompt to run (overrides default)")
    parser.add_argument("--model", default=None, help="Model ID (e.g. llamafile:Qwen3.5-0.8B-Q8_0)")
    parser.add_argument("--api-base", default=None, dest="api_base", help="Full API base URL")
    parser.add_argument("--port", type=int, default=None, help="Shorthand for http://localhost:PORT")
    parser.add_argument("--api-key", default=None, dest="api_key", help="API key")
    args = parser.parse_args()

    model_id = args.model or os.environ.get("MODEL_ID", "llamafile:Qwen3.5-0.8B-Q8_0")

    if args.api_base:
        api_base = args.api_base
    elif args.port:
        api_base = f"http://localhost:{args.port}"
    else:
        api_base = os.environ.get("API_BASE", "http://localhost:8080")

    api_key = args.api_key or os.environ.get("API_KEY", "whatever")
    prompt = args.prompt if args.prompt is not None else default_prompt

    return model_id, api_base, api_key, prompt

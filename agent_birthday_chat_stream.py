import asyncio
from pathlib import Path

from any_agent import AgentConfig
from any_llm.utils.aio import run_async_in_sync

from agent_config import get_agent_args
from streaming_tinyagent import StreamingTinyAgent


def read_file(file_name: str) -> str:
    """Read the contents of the given `file_name`.

    Args:
        file_name: The path to the file you want to read.

    Returns:
        The contents of `file_name`.
    """
    return Path(file_name).read_text()


def scan_current_dir(pattern: str) -> list[str]:
    """Scans the current directory for files satisfying the provided pattern.

    Args:
        pattern: The pattern used to filter files in the current directory (e.g. "*.txt"
        for text files, "*.py" for python files, "*.*" for all files)

    Returns:
        A string representing the list of filenames that satisfy the provided pattern
    """
    return str([str(f) for f in Path(".").glob(pattern)])


SIMPLE_INSTRUCTION = "You must use the available tools to find an answer."

BETTER_INSTRUCTION = """\
You are a file-reading assistant. The answer to questions is in files in the current directory.

Always use tools to retrieve data — never answer from memory.

When answering a question:
1. Call scan_current_dir to find relevant files (try "*.csv", "*.txt", or "*.*")
2. Call read_file on promising files to read their contents
3. Answer based only on what you actually read

If a file doesn't contain the answer, try other files before giving up.\
"""


async def main():
    model_id, api_base, api_key, _ = get_agent_args()

    agent = StreamingTinyAgent(
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=BETTER_INSTRUCTION,
            tools=[scan_current_dir, read_file],
        )
    )
    await agent._load_agent()

    history: list[tuple[str, str]] = []
    print("対話を開始します（終了: quit / exit）")

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue

        if history:
            history_text = "\n".join(
                f"User: {u}\nAssistant: {a}" for u, a in history
            )
            prompt = (
                f"Previous conversation:\n{history_text}\n"
                f"Current user message: {user_input}\n"
                "Please respond taking into account the conversation history above."
            )
        else:
            prompt = user_input

        print("\nAgent: ", end="", flush=True)
        response = await agent.run_stream_async(prompt)
        print()

        history.append((user_input, response))


run_async_in_sync(main())

from any_agent import AgentConfig
from any_llm.utils.aio import run_async_in_sync
from pathlib import Path

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
You are a file-reading assistant. The answer is in a file in the current directory.

Always use tools to retrieve data — never answer from memory.

Follow this sequence:
1. Call scan_current_dir with a pattern like "*.csv" to find data files
2. Call read_file on the relevant file to read its contents
3. Extract and report the answer from the file contents

If no matching file is found, try broader patterns such as "*.txt" or "*.*".\
"""

model_id, api_base, api_key, prompt = get_agent_args("When was Davide Eynard born?")


async def main():
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
    result = await agent.run_stream_async(prompt)
    print(f"\n\nFinal: {result}")


run_async_in_sync(main())

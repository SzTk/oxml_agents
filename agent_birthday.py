from any_agent import AgentConfig, AnyAgent
from pathlib import Path

from agent_config import get_agent_args

def read_file(file_name: str) -> str:
    """Read the contents of the given `file_name`.

    Args:
        file_name: The path to the file you want to read.

    Returns:
        The contents of `file_name`.

    Raises:
        ValueError: For the following cases:
            - If the path to the file is not allowed.
    """
    file_path = Path(file_name)
    return file_path.read_text()


def scan_current_dir(pattern: str) -> list[str]:
    """Scans the current directory for files satisfying the provided pattern.
    
    Args:
        pattern: The pattern used to filter files in the current directory (e.g. "*.txt"
        for text files, "*.py" for python files, "*.*" for all files)

    Returns:
        A string representing the list of filenames that satisfy the provided pattern
    """
    current_dir = Path(".")
    files_list = [str(f) for f in current_dir.glob(pattern)]
    return str(files_list)


model_id, api_base, api_key, prompt = get_agent_args("When was Davide Eynard born?")

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions="""You must use the available tools to find an answer. You surely have the answer in the files in the current directory, so you should use the tools to find it. You can see csv file in the current directory.""",
        tools=[scan_current_dir, read_file],
    ),
)

agent_trace = agent.run(prompt)

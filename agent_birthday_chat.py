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

model_id, api_base, api_key, prompt = get_agent_args("When was Davide Eynard born?")

def main():
    model_id, api_base, api_key, _ = get_agent_args()  # 初回プロンプトは使わない
    agent = AnyAgent.create("tinyagent", AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions=BETTER_INSTRUCTION,
        tools=[scan_current_dir, read_file],
    ))
    history = []
    print("対話を開始します（終了: quit / exit）")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        # 履歴がある場合は文脈付きプロンプトにする（any-agent 公式のやり方）
        if history:
            history_text = "\n".join(
                f"{msg.role.capitalize()}: {msg.content}"
                for msg in history
                if msg.role != "system"
            )
            prompt = f"""Previous conversation:
{history_text}
Current user message: {user_input}
Please respond taking into account the conversation history above."""
        else:
            prompt = user_input
        trace = agent.run(prompt)
        print(f"\nAgent: {trace.final_output}")
        # 次のターン用に履歴を更新
        history = trace.spans_to_messages()
if __name__ == "__main__":
    main()
# tinyagent.py に inspect を追加して置換
python3 - << 'EOF'
import re

files = [
    ".venv/lib/python3.14/site-packages/any_agent/callbacks/wrappers/tinyagent.py",
    ".venv/lib/python3.14/site-packages/any_agent/frameworks/any_agent.py",
]

for path in files:
    text = open(path).read()
    if "import inspect" not in text:
        text = text.replace("import asyncio", "import asyncio\nimport inspect", 1)
    text = text.replace("asyncio.iscoroutinefunction", "inspect.iscoroutinefunction")
    open(path, "w").write(text)
    print(f"patched: {path}")
EOF

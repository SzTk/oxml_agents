"""StreamingTinyAgent: TinyAgent with run_stream_async() for real-time token output."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from any_llm.utils.aio import run_async_in_sync
from any_agent.frameworks.tinyagent import TinyAgent
from any_agent.utils.cast import safe_cast_argument
from any_agent.logging import logger

INSIDE_NOTEBOOK = False


class StreamingTinyAgent(TinyAgent):
    """TinyAgent extended with streaming support.

    run() and run_async() work exactly as before (non-streaming).
    run_stream_async() yields typed events as tokens arrive.
    """

    async def _stream_events(
        self, completion_params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        """Convert AsyncIterator[ChatCompletionChunk] to typed event dicts.

        Yields:
            {"type": "text_delta", "text": str}
            {"type": "tool_call", "id": str, "name": str, "args": dict}
            {"type": "done"}
        """
        params = dict(completion_params)
        stream = await self.llm.acompletion(stream=True, **params)

        accumulated: dict[int, dict[str, str]] = {}

        async for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            finish_reason = choice.finish_reason

            if delta.content:
                yield {"type": "text_delta", "text": delta.content}

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in accumulated:
                        accumulated[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc.function:
                        if tc.function.name:
                            accumulated[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            accumulated[idx]["arguments"] += tc.function.arguments

            if finish_reason == "tool_calls":
                for idx in sorted(accumulated):
                    tc = accumulated[idx]
                    yield {
                        "type": "tool_call",
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": json.loads(tc["arguments"]),
                    }
                yield {"type": "done"}
                return

            if finish_reason == "stop":
                yield {"type": "done"}
                return

    async def run_stream_async(self, prompt: str) -> str:
        """Run agent with streaming; prints tokens live, returns final answer."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.instructions},
            {"role": "user", "content": prompt},
        ]

        while True:
            completion_params = dict(self.completion_params)
            completion_params["messages"] = messages

            # Mirror TinyAgent._run_async: OpenAI-compatible backends use "auto"
            # so the model can terminate with a plain text response
            if self.uses_openai:
                completion_params["tool_choice"] = "auto"

            text_parts: list[str] = []
            tool_called = False

            async for ev in self._stream_events(completion_params):
                if ev["type"] == "text_delta":
                    print(ev["text"], end="", flush=True)
                    text_parts.append(ev["text"])

                elif ev["type"] == "tool_call":
                    tool_name = ev["name"]
                    tool_args = ev["args"]

                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": ev["id"],
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_args),
                            },
                        }],
                    })

                    print(f"\n[tool: {tool_name}({tool_args})]", flush=True)

                    client = self.clients.get(tool_name)
                    if client:
                        # Cast string args to declared types (mirrors TinyAgent._run_async)
                        if hasattr(client.tool_function, "__annotations__"):
                            for arg_name, arg_type in client.tool_function.__annotations__.items():
                                if arg_name in tool_args:
                                    try:
                                        tool_args[arg_name] = safe_cast_argument(
                                            tool_args[arg_name], arg_type
                                        )
                                    except Exception as e:
                                        logger.warning(f"Failed to cast argument '{arg_name}': {e}")
                        result = await client.call_tool(
                            {"name": tool_name, "arguments": tool_args}
                        )
                    else:
                        result = f"Error: No tool found with name: {tool_name}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": ev["id"],
                        "name": tool_name,
                        "content": result,
                    })

                    if tool_name == "final_answer":
                        return result

                    tool_called = True
                    break  # restart outer while loop with updated messages

                elif ev["type"] == "done":
                    # Model returned text without a tool call → final answer
                    if not tool_called:
                        return "".join(text_parts)

    def run_stream(self, prompt: str) -> str:
        """Synchronous wrapper for run_stream_async."""
        return run_async_in_sync(
            self.run_stream_async(prompt), allow_running_loop=INSIDE_NOTEBOOK
        )

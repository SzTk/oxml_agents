import asyncio

from any_agent import AgentConfig
from any_llm.utils.aio import run_async_in_sync

from agent_config import get_agent_args
from streaming_tinyagent import StreamingTinyAgent

SECURITY_INSTRUCTIONS = """\
あなたはセキュリティの専門家です。渡されたコードの脆弱性、SQLインジェクション、認証不備などの
問題点のみを簡潔に列挙してください。\
"""

PERFORMANCE_INSTRUCTIONS = """\
あなたはパフォーマンスチューニングの専門家です。時間・空間複雑度（Big-O）、メモリリーク、
ボトルネックになる処理のみを指摘してください。\
"""

READABILITY_INSTRUCTIONS = """\
あなたはコード品質と可読性の専門家です。命名規則、コードの重複、モジュール化、DRY原則の観点から
改善点を指摘してください。\
"""

SYNTHESIZER_INSTRUCTIONS = """\
あなたはテクニカルリードです。複数の専門家から提出されたレビュー結果を元に、開発者が修正すべき
優先順位をつけた「総合コードレビューレポート」を1つにまとめて出力してください。\
"""

DEFAULT_PROMPT = """\
def get_user_data(user_id):
    import sqlite3
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # ユーザー入力を直接クエリに結合
    query = "SELECT * FROM users WHERE id = '" + str(user_id) + "'"
    cursor.execute(query)
    results = cursor.fetchall()

    # ループ内で無駄なリスト検索
    items = []
    for r in results:
        if r in items:
            pass
        else:
            items.append(r)
    return items
"""

model_id, api_base, api_key, prompt = get_agent_args(DEFAULT_PROMPT)


async def _build_agent(instructions: str) -> StreamingTinyAgent:
    agent = StreamingTinyAgent(
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=instructions,
            tools=[],
        )
    )
    await agent._load_agent()
    return agent


async def _stream_worker(agent: StreamingTinyAgent, label: str, target_code: str) -> str:
    """Stream a tool-less worker agent's tokens live, line-buffered and labeled.

    Workers here never call tools, so unlike StreamingTinyAgent.run_stream_async
    there is no tool-call loop to handle. Output is buffered per line (rather than
    printed per token) so that concurrent workers running under asyncio.gather
    don't interleave mid-line on the shared terminal.
    """
    messages = [
        {"role": "system", "content": agent.config.instructions},
        {"role": "user", "content": target_code},
    ]
    completion_params = dict(agent.completion_params)
    completion_params["messages"] = messages
    if agent.uses_openai:
        completion_params["tool_choice"] = "auto"

    full_text = ""
    line_buffer = ""
    async for ev in agent._stream_events(completion_params):
        if ev["type"] != "text_delta":
            continue
        full_text += ev["text"]
        line_buffer += ev["text"]
        while "\n" in line_buffer:
            line, line_buffer = line_buffer.split("\n", 1)
            print(f"[{label}] {line}")
    if line_buffer:
        print(f"[{label}] {line_buffer}")

    return full_text


async def main():
    security_agent = await _build_agent(SECURITY_INSTRUCTIONS)
    performance_agent = await _build_agent(PERFORMANCE_INSTRUCTIONS)
    readability_agent = await _build_agent(READABILITY_INSTRUCTIONS)
    synthesizer_agent = await _build_agent(SYNTHESIZER_INSTRUCTIONS)

    print("▶ 3つの専門エージェントで並列評価中...\n")
    security_text, performance_text, readability_text = await asyncio.gather(
        _stream_worker(security_agent, "security", prompt),
        _stream_worker(performance_agent, "performance", prompt),
        _stream_worker(readability_agent, "readability", prompt),
    )

    combined_feedback = f"""\
【セキュリティ視点からのフィードバック】:
{security_text}

【パフォーマンス視点からのフィードバック】:
{performance_text}

【可読性視点からのフィードバック】:
{readability_text}
"""

    print("\n▶ すべての評価が出揃いました。集約エージェントがレポートを作成中...\n")
    report = await synthesizer_agent.run_stream_async(
        f"以下のレビュー結果を整理・統合して最終レポートを作成してください:\n\n{combined_feedback}"
    )
    print(f"\n\n最終レポート: {report}")


run_async_in_sync(main())

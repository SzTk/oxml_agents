import asyncio

from any_agent import AgentConfig, AnyAgent
from any_llm.utils.aio import run_async_in_sync

from agent_config import get_agent_args

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


def _build_agent(instructions: str) -> AnyAgent:
    return AnyAgent.create(
        "tinyagent",
        AgentConfig(
            model_id=model_id,
            api_key=api_key,
            api_base=api_base,
            instructions=instructions,
            tools=[],
        ),
    )


security_agent = _build_agent(SECURITY_INSTRUCTIONS)
performance_agent = _build_agent(PERFORMANCE_INSTRUCTIONS)
readability_agent = _build_agent(READABILITY_INSTRUCTIONS)
synthesizer_agent = _build_agent(SYNTHESIZER_INSTRUCTIONS)


async def parallel_code_review(target_code: str) -> str:
    print("▶ 3つの専門エージェントで並列評価中...")
    security_trace, performance_trace, readability_trace = await asyncio.gather(
        security_agent.run_async(target_code),
        performance_agent.run_async(target_code),
        readability_agent.run_async(target_code),
    )

    combined_feedback = f"""\
【セキュリティ視点からのフィードバック】:
{security_trace.final_output}

【パフォーマンス視点からのフィードバック】:
{performance_trace.final_output}

【可読性視点からのフィードバック】:
{readability_trace.final_output}
"""

    print("▶ すべての評価が出揃いました。集約エージェントがレポートを作成中...")
    final_trace = await synthesizer_agent.run_async(
        f"以下のレビュー結果を整理・統合して最終レポートを作成してください:\n\n{combined_feedback}"
    )
    return final_trace.final_output


async def main():
    report = await parallel_code_review(prompt)
    print("\n================【最終レビューレポート】================")
    print(report)


run_async_in_sync(main())

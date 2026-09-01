# any-agent オントロジー制約コールバック注入デモ 設計

## 背景

`references/ontology/` にはPerplexityとの調査対話ログ（[[references/ontology/llmもしくはAIエージェントが外部リソースを利用する方法、あるいは組み込む方法について、分類したい.md]]）と、その末尾でPerplexityが生成した擬似コード `references/ontology/ontology_callback_demo.py` がある。この擬似コードは any-agent の実APIとは異なる架空のインターフェース（`llm_request.messages[0]`、`context.state`、`Callback.before_llm_call` が `None` を返す想定など）を使っており、そのままでは動作しない。

本設計は、`references/routing.py` → `agent_router.py`、`references/parallelization.py` → `agent_parallel.py` と同じ流儀で、この擬似コードを実際にインストールされている `any-agent==1.18.0` のAPIに合わせて実装し直し、「オントロジー制約をコールバックとして注入する最小デモ」をリポジトリのサンプル群に追加するもの。

## スコープ

- `agent_ontology.py`（同期版）をルートに新規作成する。
- `README_ONTOLOGY.md`（`README_ROUTER.md` と同形式、Mermaid図つき）を新規作成する。
- `README.md` のサンプル一覧テーブルに1行追加する。
- `pyproject.toml` に `rdflib` を依存追加する。
- ストリーミング版（`agent_ontology_stream.py`）は本デモのスコープ外（次のステップの候補として言及するに留める）。
- `references/ontology/ontology_callback_demo.py` は変更しない（`references/routing.py` 等と同じ「元ネタ」の位置づけとして残す）。

## 実APIの検証結果（設計の前提）

インストール済み `any_agent` 1.18.0 のソース（`frameworks/tinyagent.py`, `callbacks/wrappers/tinyagent.py`, `callbacks/span_generation/tinyagent.py`, `callbacks/context.py`, `config.py`）を直接確認し、以下を確定した。これらはPerplexity擬似コードには存在しない、実装上必須の事実。

- `Callback.before_llm_call(self, context: Context, *args, **kwargs) -> Context` / `after_llm_call` も同シグネチャ。**必ず `context` を返す**（`None` を返すと壊れる）。
- TinyAgentバックエンドでは `before_llm_call` の `kwargs` は `completion_params`（`messages`, `model`, `tools` 等）そのもの。`kwargs["messages"]` は `_run_async` 内のローカル変数 `messages` と**同一のlistオブジェクト**であり、要素をインプレースで書き換えれば（例: `messages[0]["content"] = ...`）実際のLLM呼び出しに反映される。ただし `kwargs["messages"] = 新しいlist` のような**再代入は反映されない**（呼び出しごとに新しいkwargs dictが作られるため）。
- `after_llm_call` では `args[0]` が生の `ChatCompletion`（`any_llm.types.completion`）。`args[0].choices[0].message.content` でテキストを取得する。
- コールバック間で状態を共有する場合は `context.shared`（`dict[str, Any]`）を使う。`context.state` という属性は存在しない。
- `AgentConfig(callbacks=[...])` を指定すると**デフォルトの `ConsolePrintSpan` が丸ごと置き換わる**ため、コンソール出力を残したい場合は明示的にリストへ含める必要がある（この点はPerplexity案の理解が正しかった）。

## 設計

### オントロジー定義

`ONTOLOGY_TTL`: Turtle形式の家系図オントロジー（Perplexity案の内容を維持）。`fam:Person`, `fam:Parent`（`hasChild` の `minCardinality 1` restriction）, `fam:hasChild`/`fam:hasParent`（`owl:inverseOf`）, `fam:Male`/`fam:Female`（`owl:disjointWith`）。

`ONTOLOGY_GRAPH`: モジュール読み込み時に一度だけ `rdflib.Graph().parse(data=ONTOLOGY_TTL, format="turtle")` で構築する。ここでのパース失敗（Turtle自体が壊れている）は静的アセットのバグなので握りつぶさず例外を送出する。

### コンポーネント

| コンポーネント | 役割 | 対応する any-agent の仕組み |
|---|---|---|
| `get_disjoint_pairs(graph)` | `owl:disjointWith` を辿るSPARQL `SELECT` で素なクラスの組を動的取得 | ヘルパー関数（Perplexity案の `FORBIDDEN_PATTERNS` ハードコードを廃止し、オントロジーを単一の真実源にする） |
| `query_family_ontology(query: str) -> str` | キーワードに応じ2〜3種のSPARQL `SELECT` を `ONTOLOGY_GRAPH` に実行し実結果を返す | 通常のツールとして `AgentConfig.tools` に登録 |
| `OntologyConstraintCallback` | Turtle本文＋`get_disjoint_pairs()`由来の制約説明＋「回答末尾に```turtle```フェンスで事実を追記せよ」という指示を system メッセージ先頭にインプレース注入 | `before_llm_call` |
| `OntologyValidationCallback` | 応答から```turtle```ブロックを正規表現抽出→`rdflib.Graph()`にパース→`ONTOLOGY_GRAPH`と合成→`get_disjoint_pairs()`の各組について `ASK` クエリで実際の違反を検出 | `after_llm_call` **および** `before_tool_execution`/`after_tool_execution`（詳細は下記「実装中に判明した重要な発見」を参照） |
| `ConsolePrintSpan()` | デフォルトのトレース表示を維持するため明示的に含める | `callbacks=[...]` に同梱 |

### 実装中に判明した重要な発見: `final_answer` ツール経由の最終回答とコールバックの対応関係

**これはこのデモが実際に伝えるべき教訓そのものであるため、単なるバグ修正ではなく設計判断として記録する。**

Task 7（実LLMでの手動確認）で `OntologyValidationCallback` を `after_llm_call` だけに実装した版を実行したところ、`response.choices[0].message.content` が常に空で、検証ロジックが実質発火しないことが判明した。原因は any-agent の `TinyAgent` の内部動作にある：

- `TinyAgent` は既定で `tool_choice="required"` を使う（`frameworks/tinyagent.py`）。つまりモデルは毎ターン何らかの**ツール呼び出し**を強制され、最終回答も例外ではなく `final_answer(answer: str)` というツールの呼び出しとして返る。
- `message.content` に生テキストが入るのは、モデルがツールを一切呼ばずプレーンテキストで応答した場合のみで、`tool_choice="required"` 配下の通常フローではまず起こらない。
- したがって `after_llm_call` だけを見る `OntologyValidationCallback` は、LLMが実際に書いた```turtle```ブロックを一度も目にすることなく、毎回「検証可能なスニペットが見つかりませんでした」を返し続けていた。

**これが示す教訓:** 「コールバックをどのフック点に置くか」は、注入（`before_llm_call`）と検証（応答の読み取り）とで対称ではない。書き込み側（プロンプトへの注入）は `before_llm_call` 一箇所で済むが、読み取り側（応答の検証）は、エージェントの実行系がテキストをどの経路で運ぶか（`message.content` か、ツール呼び出しの引数/戻り値か）を実際に確認しないと、コールバックが「正しく実装されているのに何も検出しない」という静かな失敗に陥る。これはコールバックベースの設計全般に通じる注意点であり、本デモの中核的な学びとして [README_ONTOLOGY.md](../../../README_ONTOLOGY.md) にも明記する。

**採用した修正:** `OntologyValidationCallback` に `before_tool_execution`/`after_tool_execution` を追加し、実行されたツールが `final_answer` だったかを `context.shared["_last_tool_name"]` で追跡した上で、`final_answer` 呼び出しの戻り値（＝LLMの最終回答テキストそのもの）に対しても同じ検証ロジック（```turtle```抽出→`find_violations`）を適用する。`after_llm_call` 側の処理は残す（`message.content` に直接テキストが入るケース、例えばモデルがツールを一切呼ばない場合にも対応するため）が、内容が空の場合は「見つかりませんでした」を毎ターン出力しないよう `if text:` で無駄な出力を抑制する。検証ロジック本体（```turtle```抽出・パース・`ASK`判定・print・`context.shared`記録）は重複を避けるため `_validate_text(context, text)` という非公開メソッドに共通化する。

### データフロー

1. `agent_config.get_agent_args()` で `model_id` / `api_base` / `api_key` / `prompt` を取得（他の `agent_*.py` と同じCloudflare relay経由の統一設定）。
2. `AgentConfig(model_id=..., api_key=..., api_base=..., instructions=..., tools=[query_family_ontology], callbacks=[OntologyConstraintCallback(), OntologyValidationCallback(), ConsolePrintSpan()])` を `AnyAgent.create("tinyagent", ...)` に渡す。
3. `agent.run(prompt)` 実行時、TinyAgentの `call_model` がラップされ、LLM呼び出しのたびに `wrap_call_model(**completion_params)` → 各コールバックの `before_llm_call(context, **kwargs)` が呼ばれる。
4. `OntologyConstraintCallback` が `kwargs["messages"][0]["content"]` をインプレースで書き換え、オントロジー制約を注入する（上記「実APIの検証結果」の通り、この変更は実際のLLM呼び出しに反映される）。
5. LLMが応答すると `after_llm_call(context, response)` が呼ばれるが、`TinyAgent` が `tool_choice="required"` で動くため、最終回答は通常 `message.content` ではなく `final_answer` ツールの呼び出し引数/戻り値として運ばれる（上記「実装中に判明した重要な発見」参照）。そのため `OntologyValidationCallback` は `before_tool_execution`/`after_tool_execution` もフックし、`final_answer` ツールが呼ばれた際にその戻り値（＝最終回答テキスト）に対して```turtle```ブロックの抽出・パース・`ASK`クエリ判定を行い `print()` する（`context.shared["ontology_violations"]` にも記録するが、本デモでは表示用途のみで読み出しはしない）。
6. `agent.run()` の戻り値 `trace.final_output` を `print()` して終了する（router/parallelと同じ末尾の書き方）。

### エラーハンドリング

- `ONTOLOGY_TTL` のパース失敗（起動時）: 握りつぶさず例外を送出する。静的アセットの不備であり実行時に回復する意味がないため。
- LLM応答から```turtle```ブロックが見つからない、または見つかっても構文が壊れている場合: `try/except` で捕捉し、「検証可能な事実が見つかりませんでした」という趣旨のメッセージを出して**処理は継続する**（このデモはベストエフォートの検証であり、LLMが毎回正しいTurtleを書ける保証はないため、パース失敗を致命的エラーにしない）。
- コールバック内の想定外の例外は any-agent 側で `AgentRunError` にラップされる標準動作に任せ、追加のハンドリングはしない。

### 依存関係

- `pyproject.toml` に `rdflib` を追加する（純Python実装、Java等の外部ランタイム不要）。
- owlready2 / HermiT のような本格的なOWL推論機は採用しない（今回の合意水準は「rdflibで実際にパースする」までであり、完全な論理推論は将来の拡張候補として README に書き添えるに留める）。

### 設定ファイル・ドキュメント

- `README_ONTOLOGY.md` を新規作成。`README_ROUTER.md` と同形式（概要文 → Mermaid `flowchart` → 「ポイント」箇条書き → 補足テーブル → サンプルプロンプト）。
- `README.md` のサンプル一覧テーブルに `agent_ontology.py` の行を追加する。

## テスト

自動テストを持たないリポジトリの流儀に合わせ、以下を手動確認する。

1. `uv run agent_ontology.py` をオントロジー違反を誘発する意図的なプロンプト（例: 同一人物をMaleかつFemaleとして扱わせようとする質問）で実行し、`OntologyValidationCallback` が違反を検出して警告を出すこと。
2. 違反を誘発しない通常のプロンプトで実行し、「違反なし」の旨が出力されること。
3. `ConsolePrintSpan` によるINPUTパネルの表示で、system メッセージ先頭にオントロジー（Turtle本文）が実際に注入されていることを目視確認する。
4. `query_family_ontology` を使うプロンプトで、固定文字列ではなく実際のSPARQLクエリ結果が返っていることを確認する。

# Brave Search API検索エージェント 設計

## 背景

`agent_duckduckgo.py`（`ddgs` ベース）は動作しているが、`ddgs` は非公式スクレイピングライブラリであり、DuckDuckGo側のbot対策次第でブロックされるリスクを構造的に抱える（[[2026-08-11-duckduckgo-search-agent-design.md]] で指摘した SearXNG の問題と同種）。Brave Search API は公式APIとして無料枠（Data for Search、月2,000クエリ）を提供しており、デモ用途には安定性の観点で優位。この設計は `agent_brave.py` を新規作成し、公式APIベースの代替を用意するためのもの。

## スコープ

- `agent_brave.py`（通常版）を新規作成する。
- ストリーミング版（`agent_brave_stream.py`）や `agent_router.py` への統合は対象外。
- 既存の `agent_searxng.py` / `agent_duckduckgo.py` 系ファイルは変更しない。

## 設計

`agent_duckduckgo.py` をベースに、`search()` 関数の実装のみを `ddgs` 呼び出しから Brave Search API（Web Search API, `GET https://api.search.brave.com/res/v1/web/search`）呼び出しに置き換える。`visit_webpage()` およびエージェント設定（`AgentConfig`, `AnyAgent.create` 呼び出し）はそのまま流用する。

### 認証

- APIキーは環境変数 `BRAVE_API_KEY` から読む（`agent_joplin.py` が `JOPLIN_TOKEN` を `os.environ` から直接読む方式を踏襲）。`get_agent_args()` が呼ばれた時点で `.env` は読み込み済みのため、`search()` 内で `os.environ.get("BRAVE_API_KEY")` すればよい。
- キー未設定時は明示的に例外を送出し、原因が分かるメッセージ（取得先URLを含む）を出す。無音で401を返すより診断しやすい。
- リクエストヘッダ: `X-Subscription-Token: <BRAVE_API_KEY>`, `Accept: application/json`。

### search() のシグネチャ

```python
def search(query: str, max_results: int = 10, time_range: str = "", safesearch: str = "moderate") -> str:
```

DuckDuckGo版とシグネチャ・デフォルト値を揃え、エージェント側の呼び出し方を変えずに済むようにする。

- `max_results`: Brave APIの `count` パラメータへマッピング。Brave API側の上限（20/リクエスト）を超えないよう `min(max_results, 20)` でクランプする。
- `time_range`: Brave APIの `freshness` パラメータへそのままマッピングする。Brave APIのネイティブ語彙（`pd`=過去24時間, `pw`=過去7日, `pm`=過去31日, `py`=過去365日、空文字で無指定）を採用し、DuckDuckGo版の `d/w/m/y` とは値が異なる点に注意（変換レイヤーは挟まない）。
- `safesearch`: Brave APIのネイティブ値（`off`/`moderate`/`strict`）をそのまま使う。DuckDuckGo版は `on/moderate/off` なので値が異なる（`strict` vs `on`）。

### データフロー

1. `requests.get(...)` でBrave Web Search APIを呼ぶ。パラメータ: `q`, `count`, `safesearch`、`time_range` が指定されていれば `freshness`。
2. レスポンスJSONの `web.results` 配列から各要素の `title` / `url` / `description` を、他エージェントと揃えた出力キー（`title` / `url` / `snippet`）にマッピングする。
3. `{"query": ..., "number_of_results": ..., "results": [...]}` の形にまとめて `json.dumps(..., indent=2)` で返す。

### エラーハンドリング

`requests` の例外（タイムアウト・HTTPエラー等）およびJSONパースエラーを捕捉し、`Exception(f"Error performing search: {e}")` として再送出する。SearXNG版・DuckDuckGo版と同じく、例外を握りつぶさずエージェント側に伝える方針を踏襲する。APIキー未設定は個別の分かりやすいメッセージで先に弾く。

### instructions文言

`BETTER_INSTRUCTION` 中の "DuckDuckGo search engine" を "Brave search engine" に変更する。それ以外の文言・シーケンス（search → visit_webpage → 報告）は変更しない。

### 依存関係

新規パッケージ依存は追加しない。`requests` は `agent_searxng.py` / `agent_duckduckgo.py` で既に直接importされており（`uv.lock` 上は他パッケージ経由の推移的依存として解決済み）、同じ流儀を踏襲する。

### 設定ファイル

- `.env.example` に `BRAVE_API_KEY=` の行を追加する（値は空、コメントで取得先URLを案内）。
- `README.md` にエージェント一覧の行と、APIキー取得方法を簡潔に案内するセクションを追加する。

## テスト

自動テストは持たないリポジトリのため、以下を手動確認する:

1. `BRAVE_API_KEY` 未設定の状態で `search()` を呼び、分かりやすい例外メッセージが出ること。
2. `BRAVE_API_KEY` を設定した状態で `uv run agent_brave.py` を実行し、`Who are the speakers for OxML 2026 MLx Cases?` のプロンプトに対してBrave検索結果を取得できること、`visit_webpage` と連携して最終回答が生成されることを確認する（実際のAPIキーが必要なため、キー未保有時はコードレビューとローカルのsyntaxチェックに留める）。

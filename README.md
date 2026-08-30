# oxml_agents
Some [any-agent](https://github.com/mozilla-ai/any-agent) examples for the OxML MLx Cases talk "Own your AI agent"

各スクリプトは、エージェントがツールを呼び出してタスクを解決する様子を示すデモです。
ツールの種類（Python 関数 / MCP サーバー）とタスクの内容を変えることで、エージェントの汎用性を示します。

## サンプル一覧

| ファイル | ツール | タスク概要 |
|---|---|---|
| `agent_birthday.py` | `scan_current_dir`, `read_file` | カレントディレクトリのファイルを走査・読み込み、Davide Eynard の誕生日を探す |
| `agent_webpage.py` | `visit_webpage` | 指定 URL のページを取得・Markdown 変換して内容を要約する |
| `agent_slides.py` | `search_web`, `visit_webpage` (any-agent 組み込み) | Web 検索とページ訪問を組み合わせ、主要なエージェンティックフレームワークを調べる |
| `agent_joplin.py` | Joplin MCP サーバー (MCPStdio) | Joplin ノートアプリの Wiki を検索し、llamafile GPU 対応の修正内容を回答する |
| `agent_zim.py` | zim-mcp-server (MCPStdio) | Zim デスクトップ Wiki を検索し、Denny Vrandecic の誕生日を探す |
| `agent_searxng.py` | `search` (SearXNG), `visit_webpage` | セルフホスト検索エンジン SearXNG を使って OxML 2026 のスピーカー情報を調べる |
| `agent_duckduckgo.py` | `search` (DuckDuckGo/ddgs), `visit_webpage` | DuckDuckGo（ddgs）を使って OxML 2026 のスピーカー情報を調べる。SearXNGがブロックされやすい問題への軽量な代替として試作 |
| `agent_brave.py` | `search` (Brave Search API), `visit_webpage` | Brave Search API を使って OxML 2026 のスピーカー情報を調べる。公式APIのため ddgs 版よりブロックに強く、無料枠（月2,000クエリ）でデモ用途には十分 |
| `agent_router.py` | `scan_current_dir`/`read_file`, `visit_webpage`, `search`（カテゴリ別） | ユーザー入力を files/webpage/search に分類し、対応する専門エージェントに委譲する（ルーターパターン） |
| `agent_parallel.py` | なし（テキストのみ） | コードレビューを security/performance/readability の3専門エージェントで並列評価し、synthesizer が1つのレポートに統合する（Parallelizationパターン） |

## 共通設定

`agent_config.py` の `get_agent_args()` が、モデル ID・API ベース URL・API キー・プロンプトを
`.env` ファイル／環境変数／CLI 引数から統一的に読み込みます。

```
uv run agent_birthday.py                          # デフォルトプロンプトで実行
uv run agent_birthday.py "..." --model gpt-4o    # プロンプトとモデルを上書き
uv run agent_birthday.py --port 8081              # ローカルサーバーのポート指定
```

`.env` ファイルで設定する場合（`.env.example` を参考に作成）：

```
MODEL_ID=anthropic:claude-sonnet-4-5
API_BASE=https://claude-workshop-relay.eyeofjapetus.workers.dev
API_KEY=workshop-0822
```

## LLM バックエンド — Cloudflare Agent Worker プロキシ（デフォルト）

デモは Cloudflare Worker でホストされた Anthropic 互換の relay（`/v1/messages`、OpenAI 形式のメッセージにも対応）経由で
Claude を呼び出します。`any-llm-sdk` の `anthropic` プロバイダーが公式 Anthropic SDK クライアントを使うため、
`x-api-key` / `anthropic-version` ヘッダーは自動的に付与されます。`MODEL_ID` は `anthropic:<model>` の形式で指定してください
（`API_BASE` に `/v1` は付けません — SDK 側が自動的に付加します）。

## LLM バックエンド — llama.cpp (Windows / Vulkan、代替)

Intel GPU（Arc 等）を活用する場合、Windows ネイティブの llama.cpp + Vulkan バックエンドを使います。
WSL2 側からは `networkingMode=mirrored` 設定により `localhost:8080` として接続できます。

**モデルのダウンロード（PowerShell）：**

```powershell
huggingface-cli download bartowski/Qwen2.5-7B-Instruct-GGUF --include "Qwen2.5-7B-Instruct-Q8_0.gguf" --local-dir 'C:\Users\takay\MyWork\llama.cpp\'
```

**サーバー起動（PowerShell）：**

```powershell
C:\Users\takay\MyWork\llama.cpp\llama-b9500-bin-win-vulkan-x64\llama-server.exe -m 'C:\Users\takay\MyWork\llama.cpp\Qwen2.5-7B-Instruct-Q8_0.gguf' -ngl 99 --port 8080
```

`-ngl 99` で全レイヤーを GPU にオフロードします。起動後、`http://localhost:8080/v1/models` で動作確認できます。

## SearXNG のセットアップ

`agent_searxng.py` の実行には SearXNG インスタンスが必要です。
Docker Compose で起動できます：

```bash
docker compose up -d
```

`searxng/settings.yml` に JSON フォーマットが有効化された設定が含まれています。

## Brave Search API のセットアップ

`agent_brave.py` の実行には Brave Search API のAPIキーが必要です。

1. https://brave.com/search/api/ でアカウント登録し、APIキーを発行する（無料枠: 月2,000クエリ）。
2. `.env` に `BRAVE_API_KEY=<発行されたキー>` を追加する（`.env.example` を参照）。

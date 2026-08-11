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
| `agent_router.py` | `scan_current_dir`/`read_file`, `visit_webpage`, `search`（カテゴリ別） | ユーザー入力を files/webpage/search に分類し、対応する専門エージェントに委譲する（ルーターパターン） |

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
MODEL_ID=openai:Qwen2.5-7B-Instruct-Q8_0
API_BASE=http://localhost:8080/v1
API_KEY=whatever
```

## LLM バックエンド — llama.cpp (Windows / Vulkan)

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

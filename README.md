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

## 共通設定

`agent_config.py` の `get_agent_args()` が、モデル ID・API ベース URL・API キー・プロンプトを
`.env` ファイル／環境変数／CLI 引数から統一的に読み込みます。
デフォルトモデルはローカル llamafile (`Qwen3.5-0.8B-Q8_0`) です。

```
python agent_birthday.py                          # デフォルトプロンプトで実行
python agent_birthday.py "..." --model gpt-4o    # プロンプトとモデルを上書き
python agent_birthday.py --port 8081              # ローカルサーバーのポート指定
```

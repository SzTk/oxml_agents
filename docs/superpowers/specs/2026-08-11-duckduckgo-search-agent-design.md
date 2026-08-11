# DuckDuckGo検索エージェント（試作）設計

## 背景

`agent_searxng.py` は自前でホストする SearXNG インスタンスをWeb検索ツールとして使うエージェントだが、SearXNG は上流の検索エンジン（Brave / Bing / Startpage / Wikidata 等）から bot 判定されブロック・CAPTCHA・レート制限を頻繁に受ける。これは設定の問題ではなく、非公式スクレイピングに対する各エンジン側の防御という構造的な問題であるため、より軽量な代替として `ddgs`（DuckDuckGo検索ライブラリ、旧 `duckduckgo-search`）を使ったエージェントをまず試作し、実用に足るか確認する。

## スコープ

- `agent_duckduckgo.py`（通常版）を新規作成する。
- ストリーミング版（`agent_duckduckgo_stream.py`）や `agent_router.py` への統合は対象外。DuckDuckGo版が実用に耐えると確認できてから別途検討する。
- 既存の SearXNG 系ファイル（`agent_searxng.py`, `agent_searxng_stream.py`, `agent_router.py`, `agent_router_stream.py`）は変更しない。

## 設計

`agent_searxng.py` をベースに、`search()` 関数の実装のみを SearXNG 呼び出しから `ddgs` 呼び出しに置き換える。`visit_webpage()` およびエージェント設定（`AgentConfig`, `AnyAgent.create` 呼び出し）はそのまま流用する。

### search() のシグネチャ

```python
def search(query: str, max_results: int = 10, time_range: str = "", safesearch: str = "moderate") -> str:
```

- `time_range`: `ddgs` のネイティブ値（`d`=日, `w`=週, `m`=月, `y`=年、空文字で無指定）をそのまま使う。SearXNG版の `day/month/year` とは語彙が異なるが、変換レイヤーは挟まず `ddgs` の語彙に合わせる。
- `safesearch`: `ddgs` のネイティブ値（`on`/`moderate`/`off`）をそのまま使う。

### データフロー

1. `DDGS().text(query, max_results=max_results, timelimit=time_range or None, safesearch=safesearch)` を呼ぶ。
2. 返ってきた各結果の `title` / `href` / `body` を、SearXNG版と揃えた出力キー（`title` / `url` / `snippet`）にマッピングする。`engine` キーは DuckDuckGo単体のため付与しない。
3. `{"query": ..., "number_of_results": ..., "results": [...]}` の形にまとめて `json.dumps(..., indent=2)` で返す。

### エラーハンドリング

`ddgs` 内部の例外（ブロック検知・タイムアウト等）を捕捉し、`Exception(f"Error performing search: {e}")` として再送出する。SearXNG版と同じく、例外を握りつぶさずエージェント側に伝える方針を踏襲する。

### instructions文言

`BETTER_INSTRUCTION` 中の "SearXNG search engine" を "DuckDuckGo search engine" に変更する。それ以外の文言・シーケンス（search → visit_webpage → 報告）は変更しない。

### 依存関係

`pyproject.toml` から未使用の `duckduckgo-search` の依存を削除する（`ddgs` のみを使うため）。

## テスト

自動テストは持たないリポジトリのため、`uv run agent_duckduckgo.py` を実行し、`Who are the speakers for OxML 2026 MLx Cases?` のプロンプトに対して DuckDuckGo検索結果を取得できること、`visit_webpage` と連携して最終回答が生成されることを手動で確認する。

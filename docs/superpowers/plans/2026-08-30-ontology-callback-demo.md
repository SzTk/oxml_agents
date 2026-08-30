# any-agent オントロジー制約コールバックデモ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** any-agent の `before_llm_call`/`after_llm_call` コールバックで、家系図オントロジー（Turtle）の制約をLLM呼び出しに注入し、応答内のTurtleスニペットをrdflibで実際に検証する最小デモ `agent_ontology.py` を作る。

**Architecture:** 単一ファイル `agent_ontology.py`（`agent_router.py`/`agent_parallel.py` と同じ薄い手続き型スクリプト構成）。`rdflib.Graph` に1度だけロードしたオントロジーを、(1) システムプロンプト注入用の制約説明の生成、(2) SPARQLベースの問い合わせツール、(3) LLM応答内Turtleスニペットの違反検出、の3箇所で共有する「単一の真実源」として使う。

**Tech Stack:** Python 3, `any-agent`（既存, tinyagentバックエンド）, `rdflib`（新規依存）, `agent_config.get_agent_args()`（既存の.env/CLI設定ローダー）。

設計の詳細・実APIの検証根拠は [docs/superpowers/specs/2026-08-30-ontology-callback-demo-design.md](../specs/2026-08-30-ontology-callback-demo-design.md) を参照。

---

## 参考: このリポジトリに自動テストフレームワークは存在しない

`agent_router.py` 等の既存デモにも pytest 等のテストは無い。そのため本プランの「テスト」ステップは、pytestではなく **`uv run python3 -c "..."` による決定的な手動検証**（LLM呼び出しを伴わない部分）と、**最終タスクでの実LLM実行による目視確認**を用いる。これは [設計ドキュメントのテスト節](../specs/2026-08-30-ontology-callback-demo-design.md#テスト) の方針と一致する。

---

### Task 1: rdflib依存の追加

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 依存を追加する**

```bash
uv add rdflib
```

これにより `pyproject.toml` の `dependencies` に `rdflib` が追加され、`uv.lock` が更新される。

- [ ] **Step 2: インストールを確認する**

Run: `uv run python3 -c "import rdflib; print(rdflib.__version__)"`
Expected: バージョン文字列が出力される（例: `7.1.4`）。エラーが出ないこと。

- [ ] **Step 3: コミット**

```bash
git add pyproject.toml uv.lock
git commit -m "add rdflib dependency for ontology callback demo"
```

---

### Task 2: オントロジー定義とグラフ構築

**Files:**
- Create: `agent_ontology.py`

- [ ] **Step 1: ファイルを作成し、オントロジー定義とグラフ構築部分を書く**

`agent_ontology.py` の内容:

```python
"""
any-agent でオントロジー制約をコールバックとして注入する最小デモ

オントロジー（家系図ドメイン）の制約を before_llm_call でプロンプトに注入し、
after_llm_call で応答内の Turtle スニペットを rdflib で検証する。

参考: references/ontology/ontology_callback_demo.py（Perplexity生成の擬似コード）。
本ファイルは実際にインストールされている any-agent==1.18.0 のAPIに合わせて
書き直したもの。設計の詳細は docs/superpowers/specs/2026-08-30-ontology-callback-demo-design.md
を参照。
"""

import re

from rdflib import Graph

# ---------------------------------------------------------------------------
# 1. オントロジー定義（Turtle）
# ---------------------------------------------------------------------------
ONTOLOGY_TTL = """
@prefix fam: <http://example.org/family#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

fam:Person a owl:Class .
fam:Parent a owl:Class ; owl:equivalentClass [ a owl:Restriction ;
    owl:onProperty fam:hasChild ; owl:minCardinality 1 ] .
fam:hasChild a owl:ObjectProperty ;
    owl:domain fam:Person ; owl:range fam:Person .
fam:hasParent a owl:ObjectProperty ;
    owl:inverseOf fam:hasChild .
fam:Male a owl:Class ; owl:disjointWith fam:Female .
fam:Female a owl:Class .
"""

ONTOLOGY_GRAPH = Graph()
ONTOLOGY_GRAPH.parse(data=ONTOLOGY_TTL, format="turtle")


def _local_name(uri: str) -> str:
    """URIの末尾のローカル名部分だけを取り出す（例: '...#Male' -> 'Male'）。"""
    return uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def get_disjoint_pairs(graph: Graph) -> list[tuple[str, str]]:
    """オントロジー中の owl:disjointWith の組を (URI, URI) のリストで返す。"""
    query = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?a ?b WHERE { ?a owl:disjointWith ?b . }
    """
    return [(str(row.a), str(row.b)) for row in graph.query(query)]


def _constraint_description() -> str:
    """プロンプトに注入する、素なクラスの組の説明文を生成する。"""
    lines = ["【重要】以下のクラスは互いに素（同じ個体が両方に属することはない）:"]
    for a, b in get_disjoint_pairs(ONTOLOGY_GRAPH):
        lines.append(f"- {_local_name(a)} と {_local_name(b)}")
    return "\n".join(lines)
```

- [ ] **Step 2: グラフ構築と disjoint 抽出を確認する**

Run:

```bash
uv run python3 -c "
from agent_ontology import ONTOLOGY_GRAPH, get_disjoint_pairs, _constraint_description
print(get_disjoint_pairs(ONTOLOGY_GRAPH))
print(_constraint_description())
"
```

Expected:

```
[('http://example.org/family#Male', 'http://example.org/family#Female')]
【重要】以下のクラスは互いに素（同じ個体が両方に属することはない）:
- Male と Female
```

- [ ] **Step 3: コミット**

```bash
git add agent_ontology.py
git commit -m "add ontology graph and disjoint-pair extraction"
```

---

### Task 3: オントロジー問い合わせツール

**Files:**
- Modify: `agent_ontology.py`（Task 2で作成したファイルに追記）

- [ ] **Step 1: `query_family_ontology` を追記する**

`agent_ontology.py` の末尾（`_constraint_description` の後）に追記:

```python
# ---------------------------------------------------------------------------
# 2. オントロジー問い合わせツール
# ---------------------------------------------------------------------------
def query_family_ontology(query: str) -> str:
    """家系図オントロジーに対してSPARQLで問い合わせる。

    Args:
        query: 自然文の質問。"parent" または "inverse" というキーワードを
            含む場合に対応するSPARQLクエリを実行する。

    Returns:
        SPARQLクエリの実行結果を整形した文字列。
    """
    q_lower = query.lower()

    if "parent" in q_lower:
        sparql = """
        PREFIX fam: <http://example.org/family#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?prop ?card WHERE {
            fam:Parent owl:equivalentClass ?restriction .
            ?restriction owl:onProperty ?prop ;
                         owl:minCardinality ?card .
        }
        """
        rows = list(ONTOLOGY_GRAPH.query(sparql))
        if not rows:
            return "オントロジーに該当する情報が見つかりませんでした。"
        prop, card = rows[0]
        return f"Parent は {_local_name(str(prop))} を {card} 個以上持つ Person です。"

    if "inverse" in q_lower:
        sparql = """
        PREFIX fam: <http://example.org/family#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?a ?b WHERE { ?a owl:inverseOf ?b . }
        """
        rows = list(ONTOLOGY_GRAPH.query(sparql))
        if not rows:
            return "オントロジーに該当する情報が見つかりませんでした。"
        a, b = rows[0]
        return f"{_local_name(str(a))} の逆関係は {_local_name(str(b))} です。"

    return "オントロジーに該当する情報が見つかりませんでした。"
```

- [ ] **Step 2: ツールの動作を確認する**

Run:

```bash
uv run python3 -c "
from agent_ontology import query_family_ontology
print(query_family_ontology('What is a parent?'))
print(query_family_ontology('What is the inverse of hasChild?'))
print(query_family_ontology('unrelated question'))
"
```

Expected:

```
Parent は hasChild を 1 個以上持つ Person です。
hasParent の逆関係は hasChild です。
オントロジーに該当する情報が見つかりませんでした。
```

（オントロジーは `fam:hasParent owl:inverseOf fam:hasChild` の向きで宣言されているため、`?a owl:inverseOf ?b` は `a=hasParent, b=hasChild` に束縛される。）

- [ ] **Step 3: コミット**

```bash
git add agent_ontology.py
git commit -m "add SPARQL-backed query_family_ontology tool"
```

---

### Task 4: Turtleスニペット抽出・違反検出（純粋関数）

**Files:**
- Modify: `agent_ontology.py`

- [ ] **Step 1: 抽出・検証ロジックを追記する**

`agent_ontology.py` の末尾（`query_family_ontology` の後）に追記:

```python
# ---------------------------------------------------------------------------
# 3. LLM応答からのTurtleスニペット抽出・検証
#    (any-agent / LLM に依存しない純粋関数)
# ---------------------------------------------------------------------------
TURTLE_BLOCK_RE = re.compile(r"```turtle\s*\n(.*?)```", re.DOTALL)

_SNIPPET_PREFIXES = (
    "@prefix fam: <http://example.org/family#> .\n"
    "@prefix ex: <http://example.org/individuals#> .\n"
)


def extract_turtle_block(text: str) -> str | None:
    """応答テキストから ```turtle フェンスコードブロックの中身を取り出す。

    見つからない場合は None を返す。
    """
    match = TURTLE_BLOCK_RE.search(text)
    if not match:
        return None
    return match.group(1).strip()


def find_violations(snippet_ttl: str) -> list[str]:
    """スニペットをオントロジーと合成し、disjointクラス違反を検出する。

    Args:
        snippet_ttl: LLMが出力したTurtleスニペット（prefix宣言は省略可）。

    Returns:
        違反を説明する文字列のリスト（空リストなら違反なし）。

    Raises:
        Exception: スニペットがTurtleとしてパースできない場合。
            呼び出し側で捕捉することを前提とする。
    """
    merged = Graph()
    merged += ONTOLOGY_GRAPH
    merged.parse(data=_SNIPPET_PREFIXES + snippet_ttl, format="turtle")

    violations = []
    for a, b in get_disjoint_pairs(ONTOLOGY_GRAPH):
        ask = f"ASK {{ ?x a <{a}> , <{b}> . }}"
        if bool(merged.query(ask)):
            violations.append(
                f"{_local_name(a)} と {_local_name(b)} を同時に持つ個体が見つかりました"
            )
    return violations
```

- [ ] **Step 2: 違反あり・違反なし・パース失敗の3ケースを確認する**

Run:

```bash
uv run python3 -c "
from agent_ontology import extract_turtle_block, find_violations

violating_text = '''Maryは女性であり、Johnは男性です。

\`\`\`turtle
ex:Mary a fam:Male, fam:Female .
\`\`\`
'''
clean_text = '''MaryはJohnの娘です。

\`\`\`turtle
ex:Mary a fam:Female .
ex:John a fam:Male .
\`\`\`
'''
no_block_text = 'Mary is John'\''s daughter.'

snippet = extract_turtle_block(violating_text)
print('violations:', find_violations(snippet))

snippet = extract_turtle_block(clean_text)
print('violations:', find_violations(snippet))

print('no block:', extract_turtle_block(no_block_text))

try:
    find_violations('this is not valid turtle {{{')
    print('ERROR: should have raised')
except Exception as e:
    print('parse error raised as expected:', type(e).__name__)
"
```

Expected:

```
violations: ['Male と Female を同時に持つ個体が見つかりました']
violations: []
no block: None
parse error raised as expected: <何らかのrdflib例外クラス名>
```

- [ ] **Step 3: コミット**

```bash
git add agent_ontology.py
git commit -m "add turtle snippet extraction and disjoint-violation checks"
```

---

### Task 5: コールバックの実装

**Files:**
- Modify: `agent_ontology.py`

- [ ] **Step 1: コールバッククラスを追記する**

`agent_ontology.py` の末尾（`find_violations` の後）に追記:

```python
# ---------------------------------------------------------------------------
# 4. コールバック
# ---------------------------------------------------------------------------
from any_agent.callbacks.base import Callback  # noqa: E402


class OntologyConstraintCallback(Callback):
    """LLM呼び出し前にオントロジー制約をシステムプロンプトに注入する。

    `context.shared["ontology_injected"]` で注入済みかを管理し、同一の
    `agent.run()` 内でツール呼び出しループにより before_llm_call が複数回
    呼ばれても、システムプロンプトに二重・多重注入しないようにする。
    """

    def before_llm_call(self, context, *args, **kwargs):
        if context.shared.get("ontology_injected"):
            return context

        messages = kwargs.get("messages")
        if not messages or messages[0].get("role") != "system":
            return context

        ontology_prompt = f"""
以下のオントロジー制約に厳密に従って回答してください。

{ONTOLOGY_TTL}

{_constraint_description()}

回答の最後に、あなたが使った・推論した個体についての事実を、以下のような
```turtle
ex:Mary a fam:Female .
```
形式の ```turtle フェンスコードブロックで追記してください。
オントロジーに明示されていない関係を推論してはいけません。
"""
        messages[0]["content"] = ontology_prompt + "\n\n" + messages[0]["content"]
        context.shared["ontology_injected"] = True
        print("[OntologyConstraintCallback] オントロジー制約をプロンプトに注入しました")
        return context


class OntologyValidationCallback(Callback):
    """LLM応答後にTurtleスニペットを抽出し、disjoint違反を検証する。"""

    def after_llm_call(self, context, *args, **kwargs):
        response = args[0]
        text = ""
        if response.choices and response.choices[0].message:
            text = response.choices[0].message.content or ""

        snippet = extract_turtle_block(text)
        if snippet is None:
            print(
                "[OntologyValidationCallback] 検証可能なTurtleスニペットが"
                "見つかりませんでした"
            )
            return context

        try:
            violations = find_violations(snippet)
        except Exception as e:
            print(f"[OntologyValidationCallback] Turtleスニペットのパースに失敗しました: {e}")
            return context

        context.shared["ontology_violations"] = violations
        if violations:
            print(f"[OntologyValidationCallback] 違反検出: {violations}")
        else:
            print("[OntologyValidationCallback] オントロジー違反は検出されませんでした")
        return context
```

**Note:** `from any_agent.callbacks.base import Callback` をファイル中間に置くのは通常のスタイルではないため、実際にはこのimportをファイル先頭のimportブロックにまとめること（`# noqa: E402` は不要になる）。Task 6でファイル冒頭のimportを整理する。

- [ ] **Step 2: 実LLM呼び出しなしでコールバックの単体動作を確認する**

`any_agent.callbacks.context.Context` を直接使い、`before_llm_call` がメッセージをインプレースで書き換えること・2回目は再注入しないことを確認する。

Run:

```bash
uv run python3 -c "
from any_agent.callbacks.context import Context
from agent_ontology import OntologyConstraintCallback, OntologyValidationCallback

ctx = Context(current_span=None, trace=None, tracer=None, shared={})
cb = OntologyConstraintCallback()

messages = [
    {'role': 'system', 'content': 'あなたは家系図オントロジーに基づいて質問に答えるアシスタントです。'},
    {'role': 'user', 'content': 'Maryは誰の娘ですか?'},
]
cb.before_llm_call(ctx, messages=messages, model='dummy')
print('injected once:', 'オントロジー制約に厳密に従って' in messages[0]['content'])
length_after_first = len(messages[0]['content'])

# 2回目の呼び出し(ツールループ内での再呼び出しを想定) — 再注入されないこと
cb.before_llm_call(ctx, messages=messages, model='dummy')
print('length unchanged after second call:', len(messages[0]['content']) == length_after_first)
"
```

Expected:

```
[OntologyConstraintCallback] オントロジー制約をプロンプトに注入しました
injected once: True
length unchanged after second call: True
```

（2回目の呼び出しでは `context.shared["ontology_injected"]` が True のため print 行は出ない）

- [ ] **Step 3: `OntologyValidationCallback` の動作をダミー応答で確認する**

```bash
uv run python3 -c "
from types import SimpleNamespace
from any_agent.callbacks.context import Context
from agent_ontology import OntologyValidationCallback

ctx = Context(current_span=None, trace=None, tracer=None, shared={})
cb = OntologyValidationCallback()

response = SimpleNamespace(
    choices=[SimpleNamespace(message=SimpleNamespace(
        content='MaryはJohnの娘です。\n\n\`\`\`turtle\nex:Mary a fam:Male, fam:Female .\n\`\`\`'
    ))]
)
cb.after_llm_call(ctx, response)
print('violations recorded:', ctx.shared['ontology_violations'])
"
```

Expected:

```
[OntologyValidationCallback] 違反検出: ['Male と Female を同時に持つ個体が見つかりました']
violations recorded: ['Male と Female を同時に持つ個体が見つかりました']
```

- [ ] **Step 4: コミット**

```bash
git add agent_ontology.py
git commit -m "add ontology constraint injection and validation callbacks"
```

---

### Task 6: importの整理とエージェント実行部分の追加

**Files:**
- Modify: `agent_ontology.py`

- [ ] **Step 1: ファイル冒頭のimportブロックを整理する**

ファイル冒頭（docstringの直後）を次のように変更する。

現在:

```python
import re

from rdflib import Graph
```

変更後:

```python
import re

from any_agent import AgentConfig, AnyAgent
from any_agent.callbacks import ConsolePrintSpan
from any_agent.callbacks.base import Callback
from rdflib import Graph

from agent_config import get_agent_args
```

そして、Task 5で追記した `from any_agent.callbacks.base import Callback  # noqa: E402` の行（コールバッククラス定義の直前にある行）を削除する。

- [ ] **Step 2: ファイル末尾にエージェント構築・実行部分を追記する**

`agent_ontology.py` の末尾（`OntologyValidationCallback` の後）に追記:

```python
# ---------------------------------------------------------------------------
# 5. エージェント設定と実行
# ---------------------------------------------------------------------------
model_id, api_base, api_key, prompt = get_agent_args(
    "John は Male であり、Mary の Parent です。Mary は John の何ですか？"
)

agent = AnyAgent.create(
    "tinyagent",
    AgentConfig(
        model_id=model_id,
        api_key=api_key,
        api_base=api_base,
        instructions="あなたは家系図オントロジーに基づいて質問に答えるアシスタントです。",
        tools=[query_family_ontology],
        callbacks=[
            OntologyConstraintCallback(),
            OntologyValidationCallback(),
            ConsolePrintSpan(),
        ],
    ),
)

trace = agent.run(prompt)
print("\n=== 最終回答 ===")
print(trace.final_output)
```

- [ ] **Step 3: importに構文エラーがないことを確認する**

Run: `uv run python3 -c "import ast; ast.parse(open('agent_ontology.py').read())"`
Expected: 何も出力されず、エラーなく終了する。

- [ ] **Step 4: コミット**

```bash
git add agent_ontology.py
git commit -m "wire up agent_ontology.py end-to-end execution"
```

---

### Task 7: 実LLMでの手動確認

**Files:** なし（`agent_ontology.py` の実行のみ）

- [ ] **Step 1: デフォルトプロンプト（違反誘発）で実行する**

Run: `uv run agent_ontology.py`

Expected（`.env` に設定済みのバックエンドに応じて文言は変わるが、以下は満たすこと）:

- コンソールに `[OntologyConstraintCallback] オントロジー制約をプロンプトに注入しました` が1回だけ出力される（ツール呼び出しループがあっても複数回出ない）。
- `ConsolePrintSpan` のINPUTパネルに、system メッセージとして `ONTOLOGY_TTL` の内容（`fam:Person a owl:Class` 等）が含まれていることを目視確認する。
- 最終回答に「Maryはhas Parent」的な正しい関係（`hasParent`の逆関係の理解）が現れる。
- `[OntologyValidationCallback]` の行が出力される（検証可能なスニペットが見つかった場合は違反有無、見つからない場合はその旨）。

- [ ] **Step 2: 違反を誘発する意地悪なプロンプトで実行する**

Run: `uv run agent_ontology.py "Johnは男性でも女性でもあります。JohnはMaryの親です。この設定に基づいて、Johnについて分かっていることを、最後にturtleブロックで事実を書きながら説明してください。"`

Expected: `[OntologyValidationCallback] 違反検出: [...]` が出力されるか、少なくともLLMがオントロジー制約（`Male`と`Female`の素性）を踏まえた回答をする（矛盾する設定を指摘する、または`turtle`ブロックで両方をassertしてしまい違反として検出される）。どちらの場合も「制約がプロンプトに実際に効いている」ことを確認できればこのステップの目的は達成。

- [ ] **Step 3: `query_family_ontology` ツールを使わせるプロンプトで実行する**

Run: `uv run agent_ontology.py "hasChildの逆の関係は何かオントロジーに問い合わせて教えてください。"`

Expected: ツール呼び出しの結果として「hasParent の逆関係は hasChild です。」のような、`query_family_ontology` が実際のSPARQLクエリ結果から生成した文字列が使われていること（固定文字列のハードコードではないこと）を確認する。

このタスクにはコミット対象の変更はない（動作確認のみ）。

**Task 7実行時に判明した重要な発見（このタスクの結果としてTask 7.5が追加された）:** Step 1で `[OntologyValidationCallback] 違反検出: [...]` が一度も出力されず、`検証可能なTurtleスニペットが見つかりませんでした` が毎ターン出力される想定外の挙動が見つかった。原因は any-agent の `TinyAgent` が `tool_choice="required"` で動作し、モデルの最終回答が `message.content` ではなく `final_answer` というツール呼び出し経由で返るため。`OntologyValidationCallback` は `after_llm_call`（`message.content` を見る）しか実装していなかったので、実際にはLLMが書いた```turtle```ブロックを一度も観測できていなかった。

これは単なるバグではなく、「コールバックをどのフック点に置くか」次第で、正しく書いたはずの検証ロジックが静かに機能しなくなるという、コールバックベースの設計そのものの重要な教訓である。詳細は [設計ドキュメントの「実装中に判明した重要な発見」](../specs/2026-08-30-ontology-callback-demo-design.md#実装中に判明した重要な発見-final_answer-ツール経由の最終回答とコールバックの対応関係) を参照。この教訓はTask 8で `README_ONTOLOGY.md` にも明記する。

---

### Task 7.5: OntologyValidationCallbackをfinal_answerツール呼び出しにも対応させる（Task 7での発見への対応）

**Files:**
- Modify: `agent_ontology.py`

- [ ] **Step 1: `OntologyValidationCallback` を書き換える**

`agent_ontology.py` 内の既存の `OntologyValidationCallback` クラス全体（`class OntologyValidationCallback(Callback):` から次の空行まで）を、以下の内容に置き換える:

```python
class OntologyValidationCallback(Callback):
    """LLM応答・最終回答からTurtleスニペットを抽出し、disjoint違反を検証する。

    TinyAgentは既定で tool_choice="required" のため、LLMの最終回答は
    message.content ではなく final_answer ツールの呼び出し経由で返る。
    そのため after_llm_call（message.content 向け）に加えて
    before_tool_execution/after_tool_execution（final_answer ツール向け）
    もフックし、どちらの経路でもTurtleスニペットを見逃さないようにする。
    """

    def _validate_text(self, context, text: str) -> None:
        snippet = extract_turtle_block(text)
        if snippet is None:
            print(
                "[OntologyValidationCallback] 検証可能なTurtleスニペットが"
                "見つかりませんでした"
            )
            return

        try:
            violations = find_violations(snippet)
        except Exception as e:
            print(f"[OntologyValidationCallback] Turtleスニペットのパースに失敗しました: {e}")
            return

        context.shared["ontology_violations"] = violations
        if violations:
            print(f"[OntologyValidationCallback] 違反検出: {violations}")
        else:
            print("[OntologyValidationCallback] オントロジー違反は検出されませんでした")

    def after_llm_call(self, context, *args, **kwargs):
        response = args[0]
        text = ""
        if response.choices and response.choices[0].message:
            text = response.choices[0].message.content or ""

        if text:
            self._validate_text(context, text)
        return context

    def before_tool_execution(self, context, *args, **kwargs):
        request = args[0] if args else {}
        context.shared["_last_tool_name"] = (
            request.get("name") if isinstance(request, dict) else None
        )
        return context

    def after_tool_execution(self, context, *args, **kwargs):
        if context.shared.get("_last_tool_name") != "final_answer":
            return context

        output = args[0] if args else ""
        self._validate_text(context, str(output))
        return context
```

- [ ] **Step 2: 実LLM呼び出しなしで新しいフックの動作を確認する**

```bash
uv run python3 -c "
from any_agent.callbacks.context import Context
from agent_ontology import OntologyValidationCallback

ctx = Context(current_span=None, trace=None, tracer=None, shared={})
cb = OntologyValidationCallback()

# final_answer 以外のツール呼び出しは無視されること
cb.before_tool_execution(ctx, {'name': 'query_family_ontology', 'arguments': {'query': 'parent'}})
cb.after_tool_execution(ctx, 'Parent は hasChild を 1 個以上持つ Person です。')
print('non-final-answer tool: violations key present?', 'ontology_violations' in ctx.shared)

# final_answer ツール呼び出しでは検証されること
final_answer_text = '''MaryはJohnの娘です。

\`\`\`turtle
ex:Mary a fam:Male, fam:Female .
\`\`\`
'''
cb.before_tool_execution(ctx, {'name': 'final_answer', 'arguments': {'answer': final_answer_text}})
cb.after_tool_execution(ctx, final_answer_text)
print('final_answer violations:', ctx.shared['ontology_violations'])

# after_llm_call は空contentでは何も検証しない（ツール呼び出しターンを想定）こと
ctx2 = Context(current_span=None, trace=None, tracer=None, shared={})
cb2 = OntologyValidationCallback()
from types import SimpleNamespace
empty_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None))])
cb2.after_llm_call(ctx2, empty_response)
print('after_llm_call with empty content skipped violations key set?', 'ontology_violations' in ctx2.shared)
"
```

Expected:

```
non-final-answer tool: violations key present? False
[OntologyValidationCallback] 違反検出: ['Male と Female を同時に持つ個体が見つかりました']
final_answer violations: ['Male と Female を同時に持つ個体が見つかりました']
after_llm_call with empty content skipped violations key set? False
```

- [ ] **Step 3: コミット**

```bash
git add agent_ontology.py
git commit -m "validate final_answer tool output, not just message.content"
```

### Task 7.6: Task 7の実LLM確認をやり直す（Step 2の再確認）

**Files:** なし（`agent_ontology.py` の実行のみ）

- [ ] **Step 1: 違反を誘発するプロンプトを再実行する**

Run: `uv run agent_ontology.py "Johnは男性でも女性でもあります。JohnはMaryの親です。この設定に基づいて、Johnについて分かっていることを、最後にturtleブロックで事実を書きながら説明してください。"`

Expected: 今度は `[OntologyValidationCallback] 違反検出: [...]` が実際に出力されること（Task 7時点では `final_answer` 経由のため検出されなかったが、Task 7.5の修正後は `final_answer` ツールの戻り値からも検証されるため検出できるはず）。LLMが turtle ブロックで両方のクラスをassertしなかった場合は検出されないこともあり得るが、その場合でも `[OntologyValidationCallback]` の行自体は（見つからない旨も含め）final_answer 経由で出力されることを確認する。

- [ ] **Step 2: デフォルトプロンプトも軽く再実行し、リグレッションがないことを確認する**

Run: `uv run agent_ontology.py`

Expected: Task 7 Step 1で確認した内容（`[OntologyConstraintCallback]` が1回だけ、最終回答が正しい）が引き続き成り立つこと。

このタスクにはコミット対象の変更はない（動作確認のみ）。

---

### Task 8: ドキュメント整備

**Files:**
- Create: `README_ONTOLOGY.md`
- Modify: `README.md`

- [ ] **Step 1: `README_ONTOLOGY.md` を作成する**

`README_ROUTER.md` と同形式（概要文 → Mermaid図 → 「ポイント」箇条書き → 補足テーブル → サンプルプロンプト）で以下の内容を書く:

```markdown
# オントロジー制約コールバックパターン（agent_ontology.py）

any-agent の `before_llm_call`/`after_llm_call` コールバックを使って、ドメインオントロジー（家系図、Turtle形式）の制約をLLM呼び出しに注入し、応答内の事実を rdflib で検証するサンプルです。`references/ontology/ontology_callback_demo.py` の擬似コード（Perplexityとの調査対話から生成）を、このリポジトリの実際の `any-agent`（1.18.0）API と `agent_config.get_agent_args()` に沿って実装し直したものが `agent_ontology.py` です。

## アーキテクチャ

\```mermaid
flowchart TD
    P["prompt<br/>get_agent_args() で取得"] --> A

    subgraph GRAPH["ONTOLOGY_GRAPH (rdflib, 起動時に1回構築)"]
        T["ONTOLOGY_TTL (Turtle)<br/>Person / Parent / Male / Female /<br/>hasChild / hasParent"]
    end

    GRAPH -.->|"get_disjoint_pairs()"| CB1
    GRAPH -.->|"SPARQL SELECT"| TOOL

    subgraph AGENT["AnyAgent (tinyagent)"]
        A["agent.run(prompt)"]
        CB1["OntologyConstraintCallback<br/>before_llm_call:<br/>system message に制約を注入<br/>(context.sharedで二重注入を防止)"]
        LLM["LLM呼び出し"]
        CB2["OntologyValidationCallback<br/>after_llm_call:<br/>応答の \`\`\`turtle ブロックを抽出し<br/>disjoint違反をASKクエリで検出"]
        TOOL["query_family_ontology<br/>(ツール, SPARQL SELECT)"]

        A --> CB1 --> LLM --> CB2
        LLM -.->|"ツール呼び出しが必要な場合"| TOOL --> LLM
    end

    CB2 --> O["trace.final_output"]
\```

**ポイント:**

- オントロジー（`ONTOLOGY_GRAPH`）は起動時に一度だけ構築され、プロンプト注入・ツール応答・違反検証の3箇所すべてで共有される「単一の真実源」です。素なクラスの組（`owl:disjointWith`）はハードコードせず `get_disjoint_pairs()` で毎回オントロジーから取得します。
- `before_llm_call` の `kwargs["messages"]` は、実行中のLLM呼び出しに使われるものと同一のlistオブジェクトです。インプレースで書き換えることで実際のプロンプトに反映されます（再代入では反映されません）。
- `context.shared` を使って「このrunで既に注入済みか」を記録し、ツール呼び出しループで `before_llm_call` が複数回呼ばれても制約テキストが多重に注入されないようにしています。
- 検証はLLM自身に応答末尾で ```turtle``` ブロックとして事実を書かせ、それをrdflibでオントロジーと合成して `ASK` クエリで矛盾を検出する方式です。厳密なOWL推論（owlready2/HermiT等）ではなく、素なクラスの同時所属のような明示的な制約違反を検出する軽量な検証です。

## 実行方法

\```bash
uv run agent_ontology.py
uv run agent_ontology.py "カスタムプロンプト"
\```

`model_id` / `api_base` / `api_key` は他のデモと同じく `agent_config.get_agent_args()`（`.env` / CLI引数）から取得します。

## 次のステップの例

- `query_family_ontology` を実SPARQLエンドポイント（Apache Jena、GraphDB等）に接続する。
- `find_violations` を owlready2 + HermiT による本格的なOWL論理推論に置き換える。
- ストリーミング版 `agent_ontology_stream.py` を作る（`agent_router_stream.py` を参考に）。
```

- [ ] **Step 2: `README.md` のサンプル一覧テーブルに1行追加する**

`README.md` の既存テーブル（`agent_parallel.py` の行の直後）に以下の行を追加する:

```markdown
| `agent_ontology.py` | `query_family_ontology`（SPARQL） | 家系図オントロジー（Turtle）の制約をコールバックでLLM呼び出しに注入し、応答内のTurtleスニペットをrdflibで検証する（オントロジー制約コールバックパターン） |
```

- [ ] **Step 3: 見た目を確認する**

`README_ONTOLOGY.md` をエディタでプレビューし、Mermaid図が崩れずに書けていること（コードフェンスの対応、インデント）を目視確認する。

- [ ] **Step 4: コミット**

```bash
git add README_ONTOLOGY.md README.md
git commit -m "document ontology callback pattern (agent_ontology.py)"
```

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

from any_agent import AgentConfig, AnyAgent
from any_agent.callbacks import ConsolePrintSpan
from any_agent.callbacks.base import Callback
from rdflib import Graph

from agent_config import get_agent_args

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


# ---------------------------------------------------------------------------
# 4. コールバック
# ---------------------------------------------------------------------------


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

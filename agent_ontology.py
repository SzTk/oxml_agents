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

#!/usr/bin/env python3
"""Attardo knowledge graph: loads, ids unique, edges resolve."""

import json

GRAPH = "comedy/theory/mined/attardo-graph.json"


class TestGraph:
    def test_loads(self):
        g = json.load(open(GRAPH))
        assert g["meta"]["id"] == "attardo-graph-v1"

    def test_kr_ranks_unique(self):
        g = json.load(open(GRAPH))
        ranks = [k["rank"] for k in g["knowledge_resources"]]
        assert sorted(ranks) == [1, 2, 3, 4, 5, 6]

    def test_lm_ids_unique_and_provenanced(self):
        g = json.load(open(GRAPH))
        ids = [m["id"] for m in g["logical_mechanisms"]]
        assert len(ids) == len(set(ids)) == 16
        provs = {m["provenance"] for m in g["logical_mechanisms"]}
        assert provs <= {"mined", "literature"}

    def test_edges_resolve(self):
        import glob as _g
        g = json.load(open(GRAPH))
        lm_ids = {m["id"] for m in g["logical_mechanisms"]}
        op_ids = set()
        d = json.load(open(
            "comedy/theory/mined/operators-v2.json"))
        for lst in (d.get("new_operators", []),
                    d.get("refinements", [])):
            for o in lst if isinstance(lst, list) else []:
                if isinstance(o, dict) and o.get("id"):
                    op_ids.add(o["id"])
        for e in g["links"]["lm_to_operators"]:
            assert e["lm"] in lm_ids, e["lm"]
            for o in e["operators"]:
                assert o in op_ids, o
            assert e["confidence"] in ("strong", "plausible")

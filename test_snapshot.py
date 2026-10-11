import os
os.environ.setdefault("CARDTRADER_TOKEN", "x")
from snapshot import diff


def test_diff():
    prev = {"1": ["1", "a"], "2": ["2", "b"]}
    assert sorted((e[0], e[1]) for e in diff(prev, [["1", "a"], ["2", "B"], ["3", "c"]])) == [("chg", "2"), ("new", "3")]
    assert [(e[0], e[1]) for e in diff(prev, [["2", "b"]])] == [("gone", "1")]

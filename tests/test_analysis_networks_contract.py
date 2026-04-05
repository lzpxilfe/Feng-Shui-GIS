import unittest

from feng_shui_gis.analysis_networks import (
    compute_stream_order,
    stream_class,
    trace_downstream_path,
)


class AnalysisNetworksContractTests(unittest.TestCase):
    def test_compute_stream_order_promotes_confluence(self):
        nodes = {
            "a": {"elev": 100},
            "b": {"elev": 90},
            "c": {"elev": 80},
            "d": {"elev": 70},
        }
        downstream = {"a": "c", "b": "c", "c": "d"}
        upstream = {"c": ["a", "b"], "d": ["c"]}
        order = compute_stream_order(nodes, downstream, upstream)
        self.assertEqual(order["a"], 1)
        self.assertEqual(order["b"], 1)
        self.assertEqual(order["c"], 2)

    def test_trace_downstream_path_stops_on_branch_or_repeat(self):
        visited = set()
        path = trace_downstream_path(
            "a",
            {"a": "b", "b": "c", "c": "d"},
            {"b": 1, "c": 2, "d": 1},
            visited,
        )
        self.assertEqual(path, ["a", "b", "c"])

    def test_stream_class_maps_order_bands(self):
        self.assertEqual(stream_class(6), "main")
        self.assertEqual(stream_class(5), "secondary")
        self.assertEqual(stream_class(4), "branch")
        self.assertEqual(stream_class(2), "minor")


if __name__ == "__main__":
    unittest.main()

import unittest

from feng_shui_gis.analysis_water import dem_step, nearest_water_distance


class _DummyDemLayer:
    def __init__(self, x_res, y_res):
        self._x_res = x_res
        self._y_res = y_res

    def rasterUnitsPerPixelX(self):
        return self._x_res

    def rasterUnitsPerPixelY(self):
        return self._y_res


class _DummyWaterGeom:
    def __init__(self, distance_from_site):
        self.distance_from_site = distance_from_site


class _DummySiteGeom:
    def __init__(self, empty=False):
        self._empty = empty

    def isEmpty(self):
        return self._empty

    def distance(self, other):
        return other.distance_from_site


class _DummyIndex:
    def __init__(self, candidate_ids, raise_type_error=False):
        self.candidate_ids = list(candidate_ids)
        self.raise_type_error = raise_type_error
        self.calls = []

    def nearestNeighbor(self, target, limit):
        self.calls.append((target, limit))
        if self.raise_type_error and len(self.calls) == 1:
            raise TypeError("geometry overload unavailable")
        return self.candidate_ids


class AnalysisWaterContractTests(unittest.TestCase):
    def test_dem_step_uses_larger_pixel_resolution(self):
        self.assertEqual(dem_step(_DummyDemLayer(10.0, 30.0)), 30.0)
        self.assertEqual(dem_step(_DummyDemLayer(0.0, 0.0)), 1.0)

    def test_nearest_water_distance_uses_smallest_candidate_distance(self):
        site_geom = _DummySiteGeom()
        water_index = _DummyIndex([1, 2])
        water_geoms = {
            1: _DummyWaterGeom(24.0),
            2: _DummyWaterGeom(12.5),
        }
        self.assertEqual(
            nearest_water_distance(site_geom, object(), water_index, water_geoms),
            12.5,
        )

    def test_nearest_water_distance_falls_back_to_point_lookup(self):
        site_geom = _DummySiteGeom()
        site_point = object()
        water_index = _DummyIndex([7], raise_type_error=True)
        water_geoms = {7: _DummyWaterGeom(9.0)}
        self.assertEqual(
            nearest_water_distance(site_geom, site_point, water_index, water_geoms),
            9.0,
        )
        self.assertIs(water_index.calls[1][0], site_point)


if __name__ == "__main__":
    unittest.main()

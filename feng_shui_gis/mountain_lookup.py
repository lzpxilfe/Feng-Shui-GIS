# -*- coding: utf-8 -*-
"""Resolve nearby mountain names from OSM Overpass using feature coordinates."""

import json
import math
import socket
import urllib.error
import urllib.parse
import urllib.request

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsMessageLog,
    Qgis,
)

from .mountain_options import mountain_options


class MountainNameService:
    OVERPASS_URL_DEFAULT = "https://overpass-api.de/api/interpreter"
    _LOG_TAG = "Feng Shui GIS MountainLookup"
    STATUS_OK = "ok"
    STATUS_NETWORK_ERROR = "network"
    STATUS_TIMEOUT_ERROR = "timeout"
    STATUS_BAD_PAYLOAD = "bad_payload"
    STATUS_NO_DATA = "no_data"
    STATUS_CACHE_HIT = "cache_hit"
    STATUS_CACHE_HIT_NO_DATA = "cache_hit_no_data"
    STATUS_BBOX_UNSUPPORTED = "bbox_unsupported"
    STATUS_UNKNOWN = "unknown"

    def __init__(self, project=None, timeout_sec=None):
        options = mountain_options()
        self.project = project or QgsProject.instance()
        self._candidate_cache = {}
        self.last_query_error = None
        self.last_query_error_code = self.STATUS_OK
        configured_timeout = options.get("request_timeout_sec", 18)
        if timeout_sec is None:
            timeout_sec = configured_timeout
        self.timeout_sec = max(5, int(timeout_sec))
        self.overpass_url = str(
            options.get("overpass_url", self.OVERPASS_URL_DEFAULT)
        ).strip() or self.OVERPASS_URL_DEFAULT
        self.max_bbox_deg = max(0.1, float(options.get("bbox_limit_deg", 3.5)))
        self.query_timeout_sec = max(5, int(options.get("query_timeout_sec", 25)))
        self.user_agent = str(
            options.get("user_agent", "FengShuiGIS-Plugin/1.0 (QGIS)")
        ).strip() or "FengShuiGIS-Plugin/1.0 (QGIS)"
        self.source_label = str(options.get("source_label", "OSM/Overpass")).strip() or "OSM/Overpass"
        self.default_radius_m = max(100.0, float(options.get("radius_default_m", 3500.0)))
        self._wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    @staticmethod
    def _log_query_warning(message):
        QgsMessageLog.logMessage(message, MountainNameService._LOG_TAG, Qgis.Warning)

    @staticmethod
    def _haversine_m(lat1, lon1, lat2, lon2):
        radius = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lam = math.radians(lon2 - lon1)
        value = (
            math.sin(d_phi / 2.0) ** 2
            + math.cos(phi1) * math.cos(phi2) * (math.sin(d_lam / 2.0) ** 2)
        )
        return 2.0 * radius * math.asin(min(1.0, math.sqrt(value)))

    def _set_query_state(self, code, message=None):
        self.last_query_error_code = code
        self.last_query_error = message
        if message:
            self._log_query_warning(message)

    @staticmethod
    def _cache_key_for_extent(extent, source_crs):
        try:
            crs_key = (
                source_crs.authid()
                if source_crs is not None and source_crs.isValid()
                else str(source_crs)
            )
            return (
                crs_key,
                round(float(extent.xMinimum()), 6),
                round(float(extent.yMinimum()), 6),
                round(float(extent.xMaximum()), 6),
                round(float(extent.yMaximum()), 6),
            )
        except (TypeError, ValueError, AttributeError):
            return None

    def _to_wgs84_point(self, point, source_crs):
        if point is None or source_crs is None:
            return None
        try:
            if source_crs == self._wgs84:
                return QgsPointXY(point.x(), point.y())
            transformer = QgsCoordinateTransform(source_crs, self._wgs84, self.project)
            transformed = transformer.transform(point)
            return QgsPointXY(transformed.x(), transformed.y())
        except (TypeError, ValueError) as exc:
            self._log_query_warning(
                f"Mountain lookup skipped: failed to transform coordinate point ({type(exc).__name__}: {exc})."
            )
            return None
        except (RuntimeError, TypeError, ValueError, OverflowError, AttributeError) as exc:
            self._log_query_warning(
                f"Mountain lookup skipped: unexpected coordinate transform error ({type(exc).__name__}: {exc})."
            )
            return None

    def fetch_candidates_for_extent(self, extent, source_crs, max_bbox_deg=None):
        if extent is None or source_crs is None:
            self._set_query_state(self.STATUS_BBOX_UNSUPPORTED, "Mountain lookup skipped: invalid extent or CRS.")
            return []
        if max_bbox_deg is None:
            max_bbox_deg = self.max_bbox_deg

        self._set_query_state(self.STATUS_OK, None)

        cache_key = self._cache_key_for_extent(extent, source_crs)
        if cache_key is not None:
            cached = self._candidate_cache.get(cache_key)
            if cached is not None:
                if cached:
                    self.last_query_error_code = self.STATUS_CACHE_HIT
                    return list(cached)
                self.last_query_error_code = self.STATUS_CACHE_HIT_NO_DATA
                self.last_query_error = (
                    f"Mountain lookup cache is empty for extent ({cache_key[0]})."
                )
                self._log_query_warning(self.last_query_error)
                return []

        corners = [
            QgsPointXY(extent.xMinimum(), extent.yMinimum()),
            QgsPointXY(extent.xMaximum(), extent.yMinimum()),
            QgsPointXY(extent.xMinimum(), extent.yMaximum()),
            QgsPointXY(extent.xMaximum(), extent.yMaximum()),
        ]
        transformed = [self._to_wgs84_point(point, source_crs) for point in corners]
        transformed = [point for point in transformed if point is not None]
        if len(transformed) < 2:
            self._set_query_state(
                self.STATUS_BBOX_UNSUPPORTED,
                "Mountain lookup skipped: failed to transform extent corners to WGS84.",
            )
            return []

        lons = [point.x() for point in transformed]
        lats = [point.y() for point in transformed]
        west, east = min(lons), max(lons)
        south, north = min(lats), max(lats)
        if (east - west) > float(max_bbox_deg) or (north - south) > float(max_bbox_deg):
            self._set_query_state(
                self.STATUS_NO_DATA,
                "Mountain lookup skipped: requested area is too large for one query.",
            )
            return []

        query = (
            f"[out:json][timeout:{self.query_timeout_sec}];"
            "("
            f'node["natural"~"peak|volcano"]["name"]({south},{west},{north},{east});'
            f'way["natural"~"peak|volcano"]["name"]({south},{west},{north},{east});'
            f'relation["natural"~"peak|volcano"]["name"]({south},{west},{north},{east});'
            f'node["place"="mountain"]["name"]({south},{west},{north},{east});'
            f'way["place"="mountain"]["name"]({south},{west},{north},{east});'
            f'relation["place"="mountain"]["name"]({south},{west},{north},{east});'
            ");"
            "out center tags;"
        )
        payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
        request = urllib.request.Request(
            self.overpass_url,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_sec) as response:
                raw = response.read().decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                self._set_query_state(
                    self.STATUS_BAD_PAYLOAD,
                    "Overpass API returned non-json payload.",
                )
                return []
        except urllib.error.HTTPError as exc:
            self._set_query_state(
                self.STATUS_NETWORK_ERROR,
                f"Overpass API HTTP error ({exc.code}): {exc.reason}",
            )
            return []
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", str(exc))
            if isinstance(reason, socket.timeout) or "timed out" in str(reason).lower():
                self._set_query_state(
                    self.STATUS_TIMEOUT_ERROR,
                    f"Overpass API request timed out: {reason}",
                )
            else:
                self._set_query_state(
                    self.STATUS_NETWORK_ERROR,
                    f"Overpass API request failed: {reason}",
                )
            return []
        except json.JSONDecodeError as exc:
            self._set_query_state(
                self.STATUS_BAD_PAYLOAD,
                f"Overpass API returned invalid JSON: {exc}",
            )
            return []
        except UnicodeDecodeError as exc:
            self._set_query_state(
                self.STATUS_BAD_PAYLOAD,
                f"Overpass API response decoding failed: {exc}",
            )
            return []
        except (RuntimeError, OSError, ValueError, TypeError) as exc:
            self._set_query_state(
                self.STATUS_UNKNOWN,
                (
                    f"Mountain lookup failed while requesting OSM service: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            return []

        candidates = []
        for item in data.get("elements", []):
            if not isinstance(item, dict):
                continue
            tags = item.get("tags", {})
            if not isinstance(tags, dict):
                continue
            name_local = str(tags.get("name", "")).strip()
            name_ko = str(tags.get("name:ko", "")).strip()
            name_en = str(tags.get("name:en", "")).strip()
            if not (name_local or name_ko or name_en):
                continue
            lat = item.get("lat")
            lon = item.get("lon")
            if lat is None or lon is None:
                center = item.get("center", {})
                lat = center.get("lat")
                lon = center.get("lon")
            try:
                lat = float(lat)
                lon = float(lon)
            except (TypeError, ValueError):
                continue
            candidates.append(
                {
                    "name_local": name_local,
                    "name_ko": name_ko,
                    "name_en": name_en,
                    "lat": lat,
                    "lon": lon,
                    "source": self.source_label,
                }
            )

        unique = {}
        for item in candidates:
            key = (
                item.get("name_local", ""),
                item.get("name_ko", ""),
                item.get("name_en", ""),
                round(item["lat"], 6),
                round(item["lon"], 6),
            )
            unique[key] = item
        normalized = list(unique.values())
        if cache_key is not None:
            self._candidate_cache[cache_key] = list(normalized)
        if normalized:
            self._set_query_state(self.STATUS_OK, None)
            return normalized
        self._set_query_state(
            self.STATUS_NO_DATA,
            "Overpass API returned no named mountain candidates for the requested extent.",
        )
        return []

    @staticmethod
    def _select_name(item, preferred_language="local"):
        preferred = str(preferred_language or "local").strip().lower()
        local_name = str(item.get("name_local", "")).strip()
        ko_name = str(item.get("name_ko", "")).strip()
        en_name = str(item.get("name_en", "")).strip()

        if preferred == "ko":
            chosen = ko_name or local_name or en_name
            used = "ko" if ko_name else ("local" if local_name else "en")
        elif preferred == "en":
            chosen = en_name or local_name or ko_name
            used = "en" if en_name else ("local" if local_name else "ko")
        else:
            chosen = local_name or ko_name or en_name
            used = "local" if local_name else ("ko" if ko_name else "en")
        if not chosen:
            return "", "unknown"
        return chosen, used

    def nearest_name(
        self,
        point,
        source_crs,
        candidates,
        max_distance_m=None,
        preferred_language="local",
    ):
        if point is None or not candidates:
            return None
        wgs_point = self._to_wgs84_point(point, source_crs)
        if wgs_point is None:
            return None

        lat = wgs_point.y()
        lon = wgs_point.x()
        if max_distance_m is None:
            max_distance_m = self.default_radius_m
        max_distance_m = max(100.0, float(max_distance_m))
        best = None
        best_distance = None
        for item in candidates:
            distance = self._haversine_m(lat, lon, item["lat"], item["lon"])
            if distance > max_distance_m:
                continue
            if best_distance is None or distance < best_distance:
                best = item
                best_distance = distance

        if best is None:
            return None
        selected_name, selected_language = self._select_name(
            best, preferred_language=preferred_language
        )
        if not selected_name:
            return None
        return {
            "name": selected_name,
            "name_local": best.get("name_local", ""),
            "name_ko": best.get("name_ko", ""),
            "name_en": best.get("name_en", ""),
            "name_language": selected_language,
            "distance_m": float(best_distance),
            "source": best.get("source", self.source_label),
        }

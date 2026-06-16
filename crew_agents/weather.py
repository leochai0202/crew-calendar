from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import requests

AWC_BASE = "https://aviationweather.gov/api/data"


@dataclass
class AirportWeather:
    icao: str
    metar: str = ""
    taf: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch_raw(endpoint: str, icao: str, timeout: int = 20) -> str:
    response = requests.get(
        f"{AWC_BASE}/{endpoint}",
        params={"ids": icao, "format": "raw"},
        headers={"User-Agent": "crew-calendar-flight-prep/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    text = response.text.strip()
    if text.startswith("No ") or "No results" in text:
        return ""
    return text


def fetch_airport_weather(icao: str, timeout: int = 20) -> AirportWeather:
    if not icao:
        return AirportWeather(icao="", error="机场 ICAO 未识别")
    weather = AirportWeather(icao=icao)
    errors: list[str] = []
    try:
        weather.metar = _fetch_raw("metar", icao, timeout)
    except Exception as exc:
        errors.append(f"METAR获取失败: {type(exc).__name__}: {exc}")
    try:
        weather.taf = _fetch_raw("taf", icao, timeout)
    except Exception as exc:
        errors.append(f"TAF获取失败: {type(exc).__name__}: {exc}")
    weather.error = "; ".join(errors)
    return weather

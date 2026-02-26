"""
Extrator de histórico de localização a partir de arquivos *LocationHistory*.json.

Arquivos como os exportados pelo Google Takeout (Location History) usam
latitudeE7 e longitudeE7: inteiros onde valor_real = valorE7 / 1e7 (graus).
Timestamp em ISO 8601 (ex: "2023-01-15T14:30:00.000Z").

Autor: Matheus C. Pestana
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# E7 = valor * 10^7 (graus em inteiro)
E7_SCALE = 1e7


def _parse_timestamp(ts: str) -> Optional[datetime]:
    """Converte string ISO 8601 para datetime (timezone-aware quando possível)."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        # Remove 'Z' e substitui por +00:00 para parsing
        normalized = ts.strip().replace("Z", "+00:00")
        if "." in normalized:
            # Python 3.11+ fromisoformat lida com fração; versões antigas podem precisar truncar
            if normalized.count(".") == 1:
                base, frac = normalized.rsplit(".", 1)
                frac = frac.replace("+", "").replace("-", "")[:6].ljust(6, "0")
                tz_part = ""
                if "+" in normalized:
                    tz_part = normalized[normalized.index("+") :]
                elif "-" in normalized and normalized.rfind("-") > 10:
                    tz_part = normalized[normalized.rfind("-") :]
                normalized = f"{base}.{frac}{tz_part}"
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _lat_lon_from_e7(latitude_e7: Optional[int], longitude_e7: Optional[int]) -> Tuple[Optional[float], Optional[float]]:
    """Converte latitudeE7 e longitudeE7 para graus (float)."""
    lat = float(latitude_e7) / E7_SCALE if latitude_e7 is not None else None
    lon = float(longitude_e7) / E7_SCALE if longitude_e7 is not None else None
    return (lat, lon)


def parse_location_history_file(file_path: Path) -> Iterator[Tuple[float, float, Optional[datetime]]]:
    """
    Lê um arquivo *LocationHistory*.json e gera (lat, lon, timestamp) por local.

    Espera JSON com lista em chave "locations" e objetos com:
    - latitudeE7, longitudeE7 (int)
    - timestamp (str ISO 8601)

    Yields:
        (lat, lon, timestamp) — timestamp pode ser None se ausente ou inválido.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Erro ao ler %s: %s", file_path, e)
        return

    locations = data.get("locations") if isinstance(data, dict) else None
    if not locations or not isinstance(locations, list):
        logger.debug("Arquivo %s sem chave 'locations' ou não é lista", file_path.name)
        return

    for item in locations:
        if not isinstance(item, dict):
            continue
        lat_e7 = item.get("latitudeE7")
        lon_e7 = item.get("longitudeE7")
        # Aceita também latitudeE7/longitudeE7 como números
        if lat_e7 is not None:
            try:
                lat_e7 = int(lat_e7)
            except (TypeError, ValueError):
                continue
        if lon_e7 is not None:
            try:
                lon_e7 = int(lon_e7)
            except (TypeError, ValueError):
                continue
        lat, lon = _lat_lon_from_e7(lat_e7, lon_e7)
        if lat is None or lon is None:
            continue
        ts = None
        if item.get("timestamp"):
            ts = _parse_timestamp(str(item["timestamp"]))
        elif item.get("timestampMs") is not None:
            try:
                ms = int(item["timestampMs"])
                ts = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                pass
        yield (lat, lon, ts)


def extract_location_history_from_dir(extract_dir: Path) -> List[Tuple[float, float, Optional[datetime]]]:
    """
    Procura por *LocationHistory*.json no diretório extraído e coleta todos os pontos.

    Args:
        extract_dir: Diretório onde o UFDR foi extraído (ex: temp/ufdr_id).

    Returns:
        Lista de (lat, lon, timestamp) para uso no banco e no mapa.
    """
    points: List[Tuple[float, float, Optional[datetime]]] = []
    pattern = "*LocationHistory*.json"
    for file_path in extract_dir.rglob(pattern):
        if not file_path.is_file():
            continue
        try:
            for lat, lon, ts in parse_location_history_file(file_path):
                points.append((lat, lon, ts))
        except Exception as e:
            logger.warning("Erro ao processar %s: %s", file_path, e)
    if points:
        logger.info("Encontrados %d pontos de localização em %s", len(points), extract_dir)
    return points

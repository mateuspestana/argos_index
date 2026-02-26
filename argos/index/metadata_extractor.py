"""
Extrator de metadados de arquivos UFDR - Identifica tipo de extração e versão Cellebrite

Autor: Matheus C. Pestana
"""

import logging
import re
import shutil
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

VERSION_PATTERN = re.compile(r'(\d+(?:\.\d+){1,})')
UFED_VERSION_PATTERN = re.compile(
    r'(?:UFED|Cellebrite|PA.?Version|UFED_PA_Version|appVersion).*?(\d+\.\d+(?:\.\d+)*)',
    re.IGNORECASE,
)


@dataclass
class UFDRMetadata:
    """Metadados extraídos de um UFDR"""
    extraction_type: str = "Desconhecido"
    cellebrite_version: Optional[str] = None


class UFDRMetadataExtractor:
    """Extrai metadados (tipo de extração, versão Cellebrite) de um UFDR extraído."""

    APPLE_KEYWORDS = [
        'iphone', 'ipad', 'ipod', 'apple', 'ios', 'macos', 'watchos',
    ]
    ANDROID_KEYWORDS = [
        'android', 'samsung', 'pixel', 'huawei', 'xiaomi', 'oneplus',
        'motorola', 'oppo', 'vivo', 'realme', 'google', 'lg', 'sony',
        'nokia', 'zte', 'lenovo', 'redmi', 'poco', 'tecno', 'infinix',
    ]

    def __init__(self, extract_dir: Path):
        self.extract_dir = extract_dir

    def extract_metadata(self) -> UFDRMetadata:
        """Orquestra a extração de metadados tentando múltiplas fontes."""
        metadata = UFDRMetadata()

        self._try_extract_from_report_xml(metadata)

        if metadata.extraction_type == "Desconhecido" or metadata.cellebrite_version is None:
            self._try_extract_from_sqlite_db(metadata)

        if metadata.extraction_type == "Desconhecido" or metadata.cellebrite_version is None:
            self._try_extract_from_pg_dump(metadata)

        if metadata.extraction_type == "Desconhecido" or metadata.cellebrite_version is None:
            self._try_extract_from_xml_files(metadata)

        if metadata.extraction_type == "Desconhecido":
            self._try_extract_from_directory_structure(metadata)

        return metadata

    # ------------------------------------------------------------------
    # Classificação Apple / Google (Android)
    # ------------------------------------------------------------------

    @classmethod
    def _classify_extraction_type(cls, device_info: str) -> str:
        if not device_info:
            return "Desconhecido"
        lower = device_info.lower()
        for kw in cls.APPLE_KEYWORDS:
            if kw in lower:
                return "Apple"
        for kw in cls.ANDROID_KEYWORDS:
            if kw in lower:
                return "Google (Android)"
        return "Desconhecido"

    @staticmethod
    def _extract_version_from_text(text: str) -> Optional[str]:
        """Tenta extrair versão do Cellebrite/UFED de uma string."""
        m = UFED_VERSION_PATTERN.search(text)
        if m:
            return m.group(1)
        return None

    # ------------------------------------------------------------------
    # 1. report.xml
    # ------------------------------------------------------------------

    def _try_extract_from_report_xml(self, metadata: UFDRMetadata) -> None:
        candidates = [
            self.extract_dir / "report.xml",
            self.extract_dir / "Report.xml",
            self.extract_dir / "report.XML",
        ]
        for candidate in candidates:
            if candidate.exists():
                self._parse_report_xml(candidate, metadata)
                if metadata.extraction_type != "Desconhecido" and metadata.cellebrite_version is not None:
                    return

    def _parse_report_xml(self, xml_path: Path, metadata: UFDRMetadata) -> None:
        try:
            tree = ET.parse(str(xml_path))
            root = tree.getroot()
            all_text = self._collect_xml_text(root)

            if metadata.cellebrite_version is None:
                metadata.cellebrite_version = self._extract_version_from_text(all_text)

            if metadata.extraction_type == "Desconhecido":
                device_text = self._find_device_text_in_xml(root)
                if device_text:
                    metadata.extraction_type = self._classify_extraction_type(device_text)

            if metadata.extraction_type == "Desconhecido":
                metadata.extraction_type = self._classify_extraction_type(all_text)

        except ET.ParseError:
            logger.debug(f"XML malformado: {xml_path}, tentando regex fallback")
            self._parse_xml_as_text(xml_path, metadata)
        except Exception as e:
            logger.debug(f"Erro ao parsear report.xml {xml_path}: {e}")

    def _collect_xml_text(self, element: ET.Element) -> str:
        parts = []
        if element.text:
            parts.append(element.text)
        if element.tail:
            parts.append(element.tail)
        for attr_val in element.attrib.values():
            parts.append(str(attr_val))
        for child in element:
            parts.append(self._collect_xml_text(child))
        return " ".join(parts)

    def _find_device_text_in_xml(self, root: ET.Element) -> Optional[str]:
        """Procura tags cujo nome contenha 'device', 'model', 'extraction' etc."""
        device_tags = [
            'devicemodel', 'devicename', 'model', 'device',
            'extractionname', 'name', 'deviceinfo',
        ]
        parts = []
        for elem in root.iter():
            tag_lower = elem.tag.lower().split('}')[-1]  # remove namespace
            if any(dt in tag_lower for dt in device_tags):
                if elem.text and elem.text.strip():
                    parts.append(elem.text.strip())
            for attr_name, attr_val in elem.attrib.items():
                if any(dt in attr_name.lower() for dt in device_tags):
                    parts.append(str(attr_val))
        return " ".join(parts) if parts else None

    def _parse_xml_as_text(self, xml_path: Path, metadata: UFDRMetadata) -> None:
        """Fallback: lê XML como texto bruto e aplica regex."""
        try:
            text = xml_path.read_text(encoding='utf-8', errors='ignore')
            if metadata.cellebrite_version is None:
                metadata.cellebrite_version = self._extract_version_from_text(text)
            if metadata.extraction_type == "Desconhecido":
                metadata.extraction_type = self._classify_extraction_type(text)
        except Exception as e:
            logger.debug(f"Erro ao ler XML como texto {xml_path}: {e}")

    # ------------------------------------------------------------------
    # 2. database.db (SQLite)
    # ------------------------------------------------------------------

    def _try_extract_from_sqlite_db(self, metadata: UFDRMetadata) -> None:
        db_paths = [
            self.extract_dir / "database.db",
            self.extract_dir / "DbData" / "database.db",
        ]
        for db_path in db_paths:
            if not db_path.exists():
                continue
            if not self._is_sqlite(db_path):
                continue
            try:
                self._query_sqlite_metadata(db_path, metadata)
            except Exception as e:
                logger.debug(f"Erro ao extrair metadados SQLite de {db_path}: {e}")

    @staticmethod
    def _is_sqlite(db_path: Path) -> bool:
        try:
            with open(db_path, 'rb') as f:
                return f.read(16).startswith(b'SQLite format 3')
        except Exception:
            return False

    def _query_sqlite_metadata(self, db_path: Path, metadata: UFDRMetadata) -> None:
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0].lower(): row[0] for row in cursor.fetchall()}

            self._try_sqlite_extraction_infos(cursor, tables, metadata)
            if metadata.extraction_type == "Desconhecido":
                self._try_sqlite_device_infos(cursor, tables, metadata)
        finally:
            conn.close()

    def _try_sqlite_extraction_infos(self, cursor, tables: dict, metadata: UFDRMetadata) -> None:
        for candidate in ['extractioninfos', 'extractioninfo', 'extraction_infos', 'extraction_info']:
            if candidate not in tables:
                continue
            real_name = tables[candidate]
            try:
                cursor.execute(f"PRAGMA table_info(\"{real_name}\")")
                columns = {col[1].lower(): col[1] for col in cursor.fetchall()}

                version_cols = [c for c in columns if 'version' in c or 'ufed' in c]
                device_cols = [c for c in columns if 'device' in c or 'model' in c or 'name' in c]

                if version_cols and metadata.cellebrite_version is None:
                    for vc in version_cols:
                        real_col = columns[vc]
                        cursor.execute(f'SELECT \"{real_col}\" FROM \"{real_name}\" WHERE \"{real_col}\" IS NOT NULL LIMIT 5')
                        for row in cursor.fetchall():
                            val = str(row[0]).strip()
                            if val:
                                v = self._extract_version_from_text(val)
                                if v:
                                    metadata.cellebrite_version = v
                                    break
                                m = VERSION_PATTERN.search(val)
                                if m:
                                    metadata.cellebrite_version = m.group(1)
                                    break
                        if metadata.cellebrite_version:
                            break

                if device_cols and metadata.extraction_type == "Desconhecido":
                    for dc in device_cols:
                        real_col = columns[dc]
                        cursor.execute(f'SELECT \"{real_col}\" FROM \"{real_name}\" WHERE \"{real_col}\" IS NOT NULL LIMIT 5')
                        for row in cursor.fetchall():
                            val = str(row[0]).strip()
                            if val:
                                et = self._classify_extraction_type(val)
                                if et != "Desconhecido":
                                    metadata.extraction_type = et
                                    break
                        if metadata.extraction_type != "Desconhecido":
                            break

            except Exception as e:
                logger.debug(f"Erro ao consultar {real_name}: {e}")

    def _try_sqlite_device_infos(self, cursor, tables: dict, metadata: UFDRMetadata) -> None:
        for candidate in ['deviceinfos', 'deviceinfo', 'device_infos', 'device_info']:
            if candidate not in tables:
                continue
            real_name = tables[candidate]
            try:
                cursor.execute(f"PRAGMA table_info(\"{real_name}\")")
                columns = {col[1].lower(): col[1] for col in cursor.fetchall()}
                relevant = [c for c in columns if any(
                    k in c for k in ['manufacturer', 'model', 'device', 'os', 'platform']
                )]
                for rc in relevant:
                    real_col = columns[rc]
                    cursor.execute(f'SELECT \"{real_col}\" FROM \"{real_name}\" WHERE \"{real_col}\" IS NOT NULL LIMIT 5')
                    for row in cursor.fetchall():
                        val = str(row[0]).strip()
                        if val:
                            et = self._classify_extraction_type(val)
                            if et != "Desconhecido":
                                metadata.extraction_type = et
                                return
            except Exception as e:
                logger.debug(f"Erro ao consultar {real_name}: {e}")

    # ------------------------------------------------------------------
    # 3. database.db (PostgreSQL dump)
    # ------------------------------------------------------------------

    def _try_extract_from_pg_dump(self, metadata: UFDRMetadata) -> None:
        db_paths = [
            self.extract_dir / "database.db",
            self.extract_dir / "DbData" / "database.db",
        ]
        for db_path in db_paths:
            if not db_path.exists():
                continue
            if self._is_sqlite(db_path):
                continue
            try:
                with open(db_path, 'rb') as f:
                    header = f.read(4)
                if not header[:2] == b'PG':
                    continue
            except Exception:
                continue

            pg_restore_path = shutil.which('pg_restore')
            if pg_restore_path:
                self._query_pg_dump_metadata(db_path, metadata)
            else:
                self._query_pg_dump_basic(db_path, metadata)

    def _query_pg_dump_metadata(self, db_path: Path, metadata: UFDRMetadata) -> None:
        schema = self._get_pg_schema(db_path)
        if not schema:
            return

        try:
            result = subprocess.run(
                ['pg_restore', '-f', '/dev/stdout', '-a',
                 f'--schema={schema}', '-t', 'ExtractionInfos', str(db_path)],
                capture_output=True, text=True, timeout=30,
            )
            in_copy = False
            for line in result.stdout.split('\n'):
                if line.startswith('COPY') and 'ExtractionInfos' in line:
                    in_copy = True
                    continue
                if in_copy:
                    if line.startswith('\\.') or not line.strip():
                        continue
                    parts = line.split('\t')
                    all_text = " ".join(p for p in parts if p and p != '\\N')

                    if metadata.cellebrite_version is None:
                        metadata.cellebrite_version = self._extract_version_from_text(all_text)

                    if metadata.extraction_type == "Desconhecido":
                        if len(parts) > 8:
                            device_name = parts[8]
                            if device_name and device_name != '\\N':
                                metadata.extraction_type = self._classify_extraction_type(device_name)
                        if metadata.extraction_type == "Desconhecido":
                            metadata.extraction_type = self._classify_extraction_type(all_text)
                    break
        except Exception as e:
            logger.debug(f"Erro ao extrair metadados do PG dump: {e}")

    def _query_pg_dump_basic(self, db_path: Path, metadata: UFDRMetadata) -> None:
        """Fallback sem pg_restore: lê bytes e busca padrões."""
        try:
            with open(db_path, 'rb') as f:
                chunk = f.read(512 * 1024)
            text = chunk.decode('utf-8', errors='ignore')

            if metadata.cellebrite_version is None:
                metadata.cellebrite_version = self._extract_version_from_text(text)
            if metadata.extraction_type == "Desconhecido":
                metadata.extraction_type = self._classify_extraction_type(text)
        except Exception as e:
            logger.debug(f"Erro ao ler PG dump para metadados: {e}")

    def _get_pg_schema(self, db_path: Path) -> Optional[str]:
        try:
            result = subprocess.run(
                ['pg_restore', '-l', str(db_path)],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.split('\n'):
                if 'SCHEMA' in line and 'device_' in line:
                    match = re.search(r'SCHEMA\s+-\s+(device_[a-f0-9-]+)', line)
                    if match:
                        return match.group(1)
        except Exception as e:
            logger.debug(f"Erro ao obter schema PG: {e}")
        return None

    # ------------------------------------------------------------------
    # 4. Qualquer XML na raiz
    # ------------------------------------------------------------------

    def _try_extract_from_xml_files(self, metadata: UFDRMetadata) -> None:
        try:
            for xml_file in self.extract_dir.glob("*.xml"):
                if xml_file.name.lower() in ('report.xml',):
                    continue
                self._parse_xml_as_text(xml_file, metadata)
                if metadata.extraction_type != "Desconhecido" and metadata.cellebrite_version is not None:
                    return
        except Exception as e:
            logger.debug(f"Erro ao varrer XMLs: {e}")

    # ------------------------------------------------------------------
    # 5. Estrutura de diretórios / nomes de arquivos
    # ------------------------------------------------------------------

    def _try_extract_from_directory_structure(self, metadata: UFDRMetadata) -> None:
        try:
            names = []
            for item in self.extract_dir.iterdir():
                names.append(item.name)
            combined = " ".join(names)
            et = self._classify_extraction_type(combined)
            if et != "Desconhecido":
                metadata.extraction_type = et
        except Exception as e:
            logger.debug(f"Erro ao analisar estrutura de diretórios: {e}")

"""
Extrator de texto de arquivos UFDR - Suporta database.db e arquivos texto

v1.1.3: Adicionado suporte a extração estruturada de dumps PostgreSQL custom (Cellebrite)
        com relacionamento de SourceInfoNodes para obter caminhos de arquivos originais.
"""

import json
import logging
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from argos.utils.text_utils import normalize_text, is_text_file

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extrator de texto de arquivos UFDR"""
    
    def __init__(self, extract_dir: Path):
        """
        Inicializa o extrator.
        
        Args:
            extract_dir: Diretório onde o UFDR foi extraído
        """
        self.extract_dir = extract_dir
    
    def extract_all(self) -> Iterator[Tuple[str, Optional[str]]]:
        """
        Extrai todo o texto disponível do UFDR.
        
        Primeiro tenta extrair de database.db, se não encontrar,
        percorre arquivos texto recursivamente.
        
        Yields:
            Tuplas (texto, source_path)
        """
        # Procura por database.db
        db_paths = [
            self.extract_dir / "database.db",
            self.extract_dir / "DbData" / "database.db"
        ]
        
        database_extracted = False
        for db_path in db_paths:
            if db_path.exists():
                logger.info(f"Encontrado database.db: {db_path}")
                try:
                    # Tenta extrair do database
                    extracted_count = 0
                    for text, source in self._extract_from_database(db_path):
                        extracted_count += 1
                        yield (text, source)
                    
                    if extracted_count > 0:
                        logger.info(f"Extraídas {extracted_count} entradas do database.db")
                        database_extracted = True
                        break  # Se conseguiu extrair, não precisa tentar outros
                    else:
                        logger.warning(f"Database.db encontrado mas nenhuma entrada extraída, tentando fallback para arquivos...")
                except Exception as e:
                    logger.error(f"Erro ao extrair do database.db {db_path}: {e}")
                    logger.info("Fazendo fallback para extração de arquivos...")
        
        # Se não conseguiu extrair do database, percorre arquivos
        if not database_extracted:
            logger.info("Extraindo texto de arquivos...")
            yield from self._extract_from_files()
    
    def _extract_from_database(self, db_path: Path) -> Iterator[Tuple[str, Optional[str]]]:
        """
        Extrai texto de um database.db (SQLite ou PostgreSQL dump).
        
        Args:
            db_path: Caminho para o database.db
        
        Yields:
            Tuplas (texto, source_path)
        """
        # Detecta tipo de arquivo
        file_type = self._detect_database_type(db_path)
        
        if file_type == "postgresql_dump":
            logger.info("Detectado PostgreSQL dump, tentando extrair texto...")
            yield from self._extract_from_postgresql_dump(db_path)
        elif file_type == "sqlite":
            logger.info("Detectado SQLite, extraindo texto...")
            yield from self._extract_from_sqlite(db_path)
        else:
            logger.warning(f"Tipo de database desconhecido: {file_type}")
            # Tenta extrair como texto genérico
            logger.info("Tentando extrair como arquivo texto genérico...")
            try:
                text = self._read_text_file(db_path)
                if text and text.strip():
                    yield (text, "database.db")
            except Exception as e:
                logger.error(f"Erro ao extrair database como texto: {e}")
                raise  # Re-raise para trigger fallback
    
    def _detect_database_type(self, db_path: Path) -> str:
        """
        Detecta o tipo de database (SQLite ou PostgreSQL dump).
        
        Args:
            db_path: Caminho para o arquivo
        
        Returns:
            str: 'sqlite', 'postgresql_dump' ou 'unknown'
        """
        try:
            # Tenta ler os primeiros bytes
            with open(db_path, 'rb') as f:
                header = f.read(16)
            
            # SQLite começa com "SQLite format 3"
            if header.startswith(b'SQLite format 3'):
                return "sqlite"
            
            # PostgreSQL dump pode começar com vários padrões
            # Verifica se é um dump custom (magic bytes PG)
            if header[:2] == b'PG':
                return "postgresql_dump"
            
            # Verifica se contém strings PostgreSQL
            try:
                with open(db_path, 'rb') as f:
                    first_1k = f.read(1024)
                    if b'PostgreSQL' in first_1k or b'pg_dump' in first_1k or b'COPY' in first_1k:
                        return "postgresql_dump"
            except Exception:
                pass
            
            # Tenta abrir como SQLite
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
                cursor.fetchone()
                conn.close()
                return "sqlite"
            except (sqlite3.DatabaseError, sqlite3.OperationalError):
                # Se falhar, pode ser PostgreSQL custom dump
                if header[:2] == b'PG' or (len(header) > 2 and header[2:4] in [b'\x00\x00', b'\x00\x01']):
                    return "postgresql_dump"
                pass
            
            return "unknown"
        except Exception as e:
            logger.error(f"Erro ao detectar tipo de database: {e}")
            return "unknown"
    
    def _extract_from_sqlite(self, db_path: Path) -> Iterator[Tuple[str, Optional[str]]]:
        """
        Extrai texto de um banco SQLite.
        
        Args:
            db_path: Caminho para o database.db
        
        Yields:
            Tuplas (texto, source_path)
        """
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Lista todas as tabelas
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                try:
                    # Lista colunas da tabela
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    
                    # Filtra colunas textuais
                    text_columns = [
                        col[1] for col in columns
                        if col[2].upper() in ('TEXT', 'VARCHAR', 'CHAR', 'CLOB', 'BLOB')
                    ]
                    
                    if not text_columns:
                        continue
                    
                    # Extrai dados de cada linha
                    for col in text_columns:
                        try:
                            cursor.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL")
                            for row in cursor.fetchall():
                                value = row[0]
                                if value:
                                    text = normalize_text(value if isinstance(value, bytes) else str(value).encode())
                                    if text:
                                        source = f"{table}.{col}"
                                        yield (text, source)
                        except Exception as e:
                            logger.debug(f"Erro ao extrair coluna {table}.{col}: {e}")
                            continue
                
                except Exception as e:
                    logger.warning(f"Erro ao processar tabela {table}: {e}")
                    continue
            
            conn.close()
        
        except Exception as e:
            logger.error(f"Erro ao extrair de SQLite {db_path}: {e}")
            raise  # Re-raise para trigger fallback para arquivos
    
    def _extract_from_postgresql_dump(self, db_path: Path) -> Iterator[Tuple[str, Optional[str]]]:
        """
        Extrai texto de um PostgreSQL dump custom (Cellebrite).

        Usa pg_restore para extrair dados estruturados e relaciona com
        SourceInfoNodes para obter os caminhos de arquivos originais.

        Args:
            db_path: Caminho para o dump

        Yields:
            Tuplas (texto, source_path)
        """
        # Verifica se pg_restore está disponível
        pg_restore_path = shutil.which('pg_restore')

        if pg_restore_path:
            logger.info("pg_restore encontrado, usando extração estruturada...")
            yield from self._extract_postgresql_structured(db_path)
        else:
            logger.warning("pg_restore não encontrado, usando extração básica...")
            yield from self._extract_postgresql_basic(db_path)

    def _get_postgresql_schema(self, db_path: Path) -> Optional[str]:
        """
        Obtém o nome do schema do dump PostgreSQL.

        Args:
            db_path: Caminho para o dump

        Returns:
            Nome do schema ou None
        """
        try:
            result = subprocess.run(
                ['pg_restore', '-l', str(db_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Procura por linhas SCHEMA
            for line in result.stdout.split('\n'):
                if 'SCHEMA' in line and 'device_' in line:
                    # Formato: "9; 2615 614635 SCHEMA - device_xxx postgres"
                    match = re.search(r'SCHEMA\s+-\s+(device_[a-f0-9-]+)', line)
                    if match:
                        return match.group(1)

            return None
        except Exception as e:
            logger.debug(f"Erro ao obter schema: {e}")
            return None

    def _extract_source_info_map(self, db_path: Path, schema: str) -> Dict[str, str]:
        """
        Extrai mapa de SourceInfoDtoId -> FilePath da tabela SourceInfoNodes.

        Args:
            db_path: Caminho para o dump
            schema: Nome do schema

        Returns:
            Dicionário {source_info_id: file_path}
        """
        source_map = {}

        try:
            result = subprocess.run(
                ['pg_restore', '-f', '/dev/stdout', '-a',
                 f'--schema={schema}', '-t', 'SourceInfoNodes', str(db_path)],
                capture_output=True,
                text=True,
                timeout=120
            )

            in_copy = False
            for line in result.stdout.split('\n'):
                if line.startswith('COPY') and 'SourceInfoNodes' in line:
                    in_copy = True
                    continue
                if in_copy:
                    if line.startswith('\\.') or line.startswith('--'):
                        in_copy = False
                        continue
                    if not line.strip():
                        continue

                    # Formato: Id\tFileName\tFilePath\t...\tSourceInfoDtoId
                    parts = line.split('\t')
                    if len(parts) >= 10:
                        file_name = parts[1]  # FileName
                        file_path = parts[2]  # FilePath
                        source_info_dto_id = parts[9]  # SourceInfoDtoId (última coluna)

                        if source_info_dto_id and source_info_dto_id != '\\N':
                            # Usa o nome do arquivo ou o caminho completo
                            path_to_use = file_name if file_name else file_path
                            if path_to_use:
                                source_map[source_info_dto_id] = path_to_use

            logger.info(f"Extraídas {len(source_map)} entradas de SourceInfoNodes")

        except subprocess.TimeoutExpired:
            logger.warning("Timeout ao extrair SourceInfoNodes")
        except Exception as e:
            logger.warning(f"Erro ao extrair SourceInfoNodes: {e}")

        return source_map

    def _get_extraction_name(self, db_path: Path, schema: str) -> Optional[str]:
        """
        Obtém o nome da extração/dispositivo da tabela ExtractionInfos.

        Args:
            db_path: Caminho para o dump
            schema: Nome do schema

        Returns:
            Nome da extração ou None
        """
        try:
            result = subprocess.run(
                ['pg_restore', '-f', '/dev/stdout', '-a',
                 f'--schema={schema}', '-t', 'ExtractionInfos', str(db_path)],
                capture_output=True,
                text=True,
                timeout=30
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
                    if len(parts) > 8:
                        # DeviceName está na posição 8
                        device_name = parts[8]
                        if device_name and device_name != '\\N':
                            return device_name
                    break

        except Exception as e:
            logger.debug(f"Erro ao obter nome da extração: {e}")

        return None

    def _get_tables_with_text(self, db_path: Path, schema: str) -> List[Tuple[str, List[str], Optional[int]]]:
        """
        Lista tabelas que têm colunas de texto e identifica posição de SourceInfoId.

        Args:
            db_path: Caminho para o dump
            schema: Nome do schema

        Returns:
            Lista de (table_name, text_columns, source_info_id_position)
        """
        tables = []

        try:
            result = subprocess.run(
                ['pg_restore', '-l', str(db_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Extrai nomes de tabelas com dados
            table_names = set()
            for line in result.stdout.split('\n'):
                if 'TABLE DATA' in line and schema in line:
                    # Formato: "5684; 0 616151 TABLE DATA device_xxx TableName postgres"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'DATA' and i + 2 < len(parts):
                            table_name = parts[i + 2]
                            if table_name != 'postgres':
                                table_names.add(table_name)

            # Para cada tabela, obtém estrutura e identifica colunas de texto
            for table_name in sorted(table_names):
                try:
                    result = subprocess.run(
                        ['pg_restore', '-f', '/dev/stdout',
                         f'--schema={schema}', '-t', table_name, str(db_path)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                    # Procura CREATE TABLE para identificar colunas
                    text_columns = []
                    source_info_pos = None
                    col_index = 0

                    in_create = False
                    for line in result.stdout.split('\n'):
                        if 'CREATE TABLE' in line:
                            in_create = True
                            continue
                        if in_create:
                            if line.strip().startswith(');'):
                                in_create = False
                                break

                            # Parse coluna
                            line_stripped = line.strip().rstrip(',')
                            if line_stripped.startswith('"'):
                                col_match = re.match(r'"([^"]+)"\s+(\w+)', line_stripped)
                                if col_match:
                                    col_name = col_match.group(1)
                                    col_type = col_match.group(2).lower()

                                    if col_name == 'SourceInfoId':
                                        source_info_pos = col_index

                                    if col_type == 'text':
                                        text_columns.append((col_name, col_index))

                                    col_index += 1

                    if text_columns:
                        tables.append((table_name, text_columns, source_info_pos))

                except Exception as e:
                    logger.debug(f"Erro ao analisar tabela {table_name}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Erro ao listar tabelas: {e}")

        return tables

    def _extract_postgresql_structured(self, db_path: Path) -> Iterator[Tuple[str, Optional[str]]]:
        """
        Extrai dados estruturados de dump PostgreSQL usando pg_restore.

        Args:
            db_path: Caminho para o dump

        Yields:
            Tuplas (texto, source_path)
        """
        # Obtém schema
        schema = self._get_postgresql_schema(db_path)
        if not schema:
            logger.warning("Schema não encontrado, usando extração básica")
            yield from self._extract_postgresql_basic(db_path)
            return

        logger.info(f"Schema encontrado: {schema}")

        # Obtém nome da extração para contexto
        extraction_name = self._get_extraction_name(db_path, schema)
        if extraction_name:
            logger.info(f"Extração identificada: {extraction_name}")

        # Extrai mapa de SourceInfoNodes
        source_map = self._extract_source_info_map(db_path, schema)

        # Obtém tabelas com colunas de texto
        tables = self._get_tables_with_text(db_path, schema)
        logger.info(f"Encontradas {len(tables)} tabelas com colunas de texto")

        extracted_count = 0
        source_info_resolved = 0

        for table_name, text_columns, source_info_pos in tables:
            try:
                result = subprocess.run(
                    ['pg_restore', '-f', '/dev/stdout', '-a',
                     f'--schema={schema}', '-t', table_name, str(db_path)],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                in_copy = False
                for line in result.stdout.split('\n'):
                    if line.startswith('COPY') and table_name in line:
                        in_copy = True
                        continue
                    if in_copy:
                        if line.startswith('\\.') or line.startswith('--'):
                            in_copy = False
                            continue
                        if not line.strip():
                            continue

                        parts = line.split('\t')

                        # Determina source_path
                        # Formato padrão: "database.db:NomeTabela" para indicar origem do dump
                        source_path = f"database.db:{table_name}"
                        resolved_from_map = False

                        # Tenta obter do SourceInfoNodes
                        if source_info_pos is not None and source_info_pos < len(parts):
                            source_info_id = parts[source_info_pos]
                            if source_info_id and source_info_id != '\\N':
                                if source_info_id in source_map:
                                    source_path = source_map[source_info_id]
                                    resolved_from_map = True
                                    source_info_resolved += 1

                        # Extrai valores das colunas de texto
                        for col_name, col_index in text_columns:
                            if col_index < len(parts):
                                value = parts[col_index]
                                if value and value != '\\N':
                                    # Decodifica escapes do PostgreSQL
                                    text = self._decode_pg_text(value)
                                    if text and text.strip():
                                        extracted_count += 1
                                        yield (text, source_path)

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout ao extrair tabela {table_name}")
            except Exception as e:
                logger.debug(f"Erro ao extrair tabela {table_name}: {e}")
                continue

        logger.info(f"Extraídas {extracted_count} entradas do dump PostgreSQL estruturado")
        if source_info_resolved > 0:
            logger.info(f"Resolvidos {source_info_resolved} source_paths via SourceInfoNodes")

    def _decode_pg_text(self, text: str) -> str:
        """
        Decodifica escapes de texto do PostgreSQL.

        Args:
            text: Texto com escapes PostgreSQL

        Returns:
            Texto decodificado
        """
        if not text:
            return text

        # Substitui escapes comuns
        text = text.replace('\\n', '\n')
        text = text.replace('\\t', '\t')
        text = text.replace('\\r', '\r')
        text = text.replace('\\\\', '\\')

        return text

    def _extract_postgresql_basic(self, db_path: Path) -> Iterator[Tuple[str, Optional[str]]]:
        """
        Extração básica de dump PostgreSQL (fallback quando pg_restore não está disponível).

        Args:
            db_path: Caminho para o dump

        Yields:
            Tuplas (texto, source_path)
        """
        try:
            with open(db_path, 'rb') as f:
                content = f.read()

            # Normaliza o conteúdo
            text = normalize_text(content)

            # Tenta extrair dados INSERT (formato comum em dumps)
            insert_pattern = r"INSERT INTO\s+\w+\s+.*?VALUES\s*\((.*?)\);"

            matches = list(re.finditer(insert_pattern, text, re.IGNORECASE | re.DOTALL))
            for match in matches:
                values_text = match.group(1)
                # Remove aspas e extrai valores
                cleaned = re.sub(r"['\"]", '', values_text)
                if cleaned.strip():
                    yield (cleaned, "postgresql_dump")

            # Se não encontrou INSERTs, retorna o texto completo (limitado)
            if not matches:
                # Limita tamanho para evitar textos gigantes
                if len(text) > 1000000:  # 1MB
                    text = text[:1000000]
                if text.strip():
                    yield (text, "postgresql_dump")

        except Exception as e:
            logger.error(f"Erro ao extrair de PostgreSQL dump {db_path}: {e}")
            raise
    
    def _extract_from_files(self) -> Iterator[Tuple[str, Optional[str]]]:
        """
        Percorre arquivos recursivamente e extrai texto.
        
        Yields:
            Tuplas (texto, source_path)
        """
        # Extensões de arquivo texto suportadas
        text_extensions = {
            # Texto puro
            '.txt', '.log', '.md', '.markdown', '.rst',
            # Estrutura de dados
            '.json', '.xml', '.yaml', '.yml', '.toml',
            # Dados tabulares
            '.csv', '.tsv',
            # Email
            '.eml', '.msg',
            # Web
            '.html', '.htm', '.xhtml',
            # Contatos
            '.vcf', '.vcs',
            # Outros
            '.ini', '.cfg', '.conf', '.properties', '.env',
            # Código (pode conter dados)
            '.py', '.js', '.java', '.cpp', '.c', '.h', '.php', '.rb', '.go',
            '.sql', '.sh', '.bash', '.zsh', '.ps1', '.bat', '.cmd'
        }
        
        extracted_count = 0
        for file_path in self.extract_dir.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Ignora arquivos muito grandes (acima de 50MB)
            try:
                if file_path.stat().st_size > 50 * 1024 * 1024:
                    logger.debug(f"Ignorando arquivo muito grande: {file_path.name} ({file_path.stat().st_size / 1024 / 1024:.1f}MB)")
                    continue
            except Exception:
                pass
            
            # Verifica extensão ou se é arquivo texto conhecido
            if file_path.suffix.lower() in text_extensions or is_text_file(str(file_path)):
                try:
                    text = self._read_text_file(file_path)
                    if text and text.strip():
                        # Caminho relativo ao extract_dir
                        source_path = str(file_path.relative_to(self.extract_dir))
                        extracted_count += 1
                        yield (text, source_path)
                except Exception as e:
                    logger.debug(f"Erro ao ler arquivo {file_path}: {e}")
                    continue
        
        logger.info(f"Extraídos {extracted_count} arquivos de texto")
    
    def _read_text_file(self, file_path: Path) -> Optional[str]:
        """
        Lê um arquivo de texto e normaliza.
        
        Args:
            file_path: Caminho do arquivo
        
        Returns:
            str: Texto normalizado ou None se erro
        """
        try:
            # Tenta ler como texto primeiro
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return normalize_text(content.encode('utf-8'))
            except UnicodeDecodeError:
                # Se falhar, lê como bytes e normaliza
                with open(file_path, 'rb') as f:
                    content = f.read()
                return normalize_text(content)
        except Exception as e:
            logger.debug(f"Erro ao ler arquivo {file_path}: {e}")
            return None


"""
Extrator de texto de arquivos UFDR - Suporta database.db e arquivos texto
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

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
        Extrai texto de um PostgreSQL dump (best-effort).
        
        Nota: PostgreSQL dumps são complexos. Esta implementação
        tenta extrair texto de forma básica.
        
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
            import re
            insert_pattern = r"INSERT INTO\s+\w+\s+.*?VALUES\s*\((.*?)\);"
            
            matches = re.finditer(insert_pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                values_text = match.group(1)
                # Remove aspas e extrai valores
                cleaned = re.sub(r"['\"]", '', values_text)
                if cleaned.strip():
                    yield (cleaned, "postgresql_dump")
            
            # Se não encontrou INSERTs, retorna o texto completo (limitado)
            if not any(True for _ in matches):
                # Limita tamanho para evitar textos gigantes
                if len(text) > 1000000:  # 1MB
                    text = text[:1000000]
                if text.strip():
                    yield (text, "postgresql_dump")
        
        except Exception as e:
            logger.error(f"Erro ao extrair de PostgreSQL dump {db_path}: {e}")
            raise  # Re-raise para trigger fallback para arquivos
            raise  # Re-raise para trigger fallback para arquivos
    
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


"""
Camada de persistência - Gerencia banco de dados SQLite ou MySQL
"""

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import (
    Boolean, BigInteger, CHAR, Column, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, create_engine, text
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.exc import SQLAlchemyError

from argos.config import get_database_url, DB_TYPE

logger = logging.getLogger(__name__)

Base = declarative_base()


class UFDRFile(Base):
    """Tabela de arquivos UFDR processados"""
    __tablename__ = "ufdr_files"

    id = Column(CHAR(64), primary_key=True, comment="Hash SHA-256 do arquivo")
    filename = Column(Text, nullable=False, comment="Nome original do arquivo")
    source = Column(Text, nullable=True, comment="Origem do arquivo")
    full_path = Column(Text, nullable=True, comment="Caminho completo do UFDR no disco")
    extraction_type = Column(String(50), nullable=True, comment="Tipo de extração: Apple, Google (Android), Desconhecido")
    cellebrite_version = Column(String(50), nullable=True, comment="Versão do Cellebrite UFED utilizada")
    processed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), comment="Timestamp de processamento")
    status = Column(String(20), nullable=False, default="processed", comment="Status: processed, error")
    
    # Relacionamentos
    text_entries = relationship("TextEntry", back_populates="ufdr_file", cascade="all, delete-orphan")
    regex_hits = relationship("RegexHit", back_populates="ufdr_file", cascade="all, delete-orphan")
    location_points = relationship("LocationPoint", back_populates="ufdr_file", cascade="all, delete-orphan")


class LocationPoint(Base):
    """Pontos de histórico de localização (ex.: Google Location History)."""
    __tablename__ = "location_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ufdr_id = Column(CHAR(64), ForeignKey("ufdr_files.id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    point_at = Column(DateTime, nullable=True, comment="Data/hora do ponto (quando disponível)")
    source_path = Column(Text, nullable=True, comment="Caminho do arquivo JSON de origem no UFDR")

    ufdr_file = relationship("UFDRFile", back_populates="location_points")
    __table_args__ = (Index("idx_location_points_ufdr", "ufdr_id"),)


class TextEntry(Base):
    """Tabela de entradas de texto extraídas"""
    __tablename__ = "text_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ufdr_id = Column(CHAR(64), ForeignKey("ufdr_files.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False, comment="Texto bruto extraído")
    source_path = Column(Text, nullable=True, comment="Caminho interno no UFDR")
    source_name = Column(Text, nullable=True, comment="Nome do arquivo (último segmento do source_path)")
    full_source_path = Column(Text, nullable=True, comment="Caminho completo do arquivo interno (UFDR + source_path)")
    file_md5 = Column(CHAR(32), nullable=True, comment="Hash MD5 do arquivo interno de onde o texto foi extraído")
    indexed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), comment="Timestamp de indexação")
    
    # Relacionamentos
    ufdr_file = relationship("UFDRFile", back_populates="text_entries")
    
    # Índice FULLTEXT para SQLite (FTS5) ou MySQL
    __table_args__ = (
        Index('idx_text_content_fts', 'content', mysql_prefix='FULLTEXT'),
    )


class RegexHit(Base):
    """Tabela de hits de regex encontrados"""
    __tablename__ = "regex_hits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ufdr_id = Column(CHAR(64), ForeignKey("ufdr_files.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(100), nullable=False, index=True, comment="Tipo do padrão (ex: BR_CPF, EMAIL)")
    value = Column(Text, nullable=False, index=True, comment="Valor encontrado")
    validated = Column(Boolean, nullable=False, default=False, comment="Se passou por validação lógica")
    context = Column(Text, nullable=True, comment="Trecho de contexto próximo")
    source_path = Column(Text, nullable=True, comment="Caminho interno no UFDR onde o hit foi encontrado")
    file_md5 = Column(CHAR(32), nullable=True, comment="Hash MD5 do arquivo interno onde o hit foi encontrado")
    
    # Relacionamentos
    ufdr_file = relationship("UFDRFile", back_populates="regex_hits")
    
    # Índices adicionais
    __table_args__ = (
        Index('idx_regex_type_value', 'type', 'value'),
    )


class DatabaseManager:
    """Gerenciador de banco de dados"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Inicializa o gerenciador de banco de dados.
        
        Args:
            database_url: URL de conexão (opcional, usa config padrão se não fornecido)
        """
        self.database_url = database_url or get_database_url()
        
        # Configura engine com pool de conexões
        connect_args = {}
        if DB_TYPE == "sqlite":
            connect_args = {"check_same_thread": False}
            # Habilita FTS5 para SQLite e desabilita RETURNING para compatibilidade
            self.engine = create_engine(
                self.database_url,
                connect_args=connect_args,
                echo=False,
                # Desabilita RETURNING para SQLite (não suportado em versões antigas)
                execution_options={"sqlite_autoincrement": True}
            )
        else:
            self.engine = create_engine(
                self.database_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False
            )
        
        # Configura sessionmaker com expire_on_commit=False para evitar problemas com objetos detached
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
    def create_tables(self):
        """Cria todas as tabelas do schema se não existirem e aplica migrações pendentes."""
        try:
            Base.metadata.create_all(self.engine, checkfirst=True)
            if DB_TYPE == "sqlite":
                self._migrate_sqlite_schema_v1_2()
            logger.info("Tabelas verificadas/criadas com sucesso")
        except SQLAlchemyError as e:
            logger.error(f"Erro ao criar tabelas: {e}")
            raise

    def _migrate_sqlite_schema_v1_2(self) -> None:
        """Adiciona colunas da v1.2.0 em bancos SQLite existentes (idempotente)."""
        migrations = [
            ("ufdr_files", "extraction_type", "VARCHAR(50)"),
            ("ufdr_files", "cellebrite_version", "VARCHAR(50)"),
            ("text_entries", "file_md5", "CHAR(32)"),
            ("regex_hits", "file_md5", "CHAR(32)"),
        ]
        with self.engine.connect() as conn:
            for table, column, col_type in migrations:
                try:
                    result = conn.execute(
                        text(f"PRAGMA table_info({table})")
                    )
                    existing = {row[1] for row in result.fetchall()}
                    if column not in existing:
                        conn.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                        )
                        conn.commit()
                        logger.info(f"Migração 1.2.0: coluna {table}.{column} adicionada")
                except SQLAlchemyError as e:
                    logger.warning(f"Migração {table}.{column}: {e}")
                    conn.rollback()
    
    def get_session(self) -> Session:
        """Retorna uma nova sessão do banco de dados"""
        return self.SessionLocal()
    
    def add_ufdr_file(
        self,
        ufdr_id: str,
        filename: str,
        source: Optional[str] = None,
        full_path: Optional[str] = None,
        extraction_type: Optional[str] = None,
        cellebrite_version: Optional[str] = None,
        status: str = "processed"
    ) -> UFDRFile:
        """
        Adiciona ou atualiza um arquivo UFDR.

        Args:
            ufdr_id: Hash SHA-256 do arquivo
            filename: Nome do arquivo
            source: Origem do arquivo
            full_path: Caminho completo do UFDR no disco (opcional; se None, montado de source/filename)
            extraction_type: Tipo de extração (Apple, Google (Android), Desconhecido)
            cellebrite_version: Versão do Cellebrite UFED
            status: Status (processed, error)

        Returns:
            UFDRFile: Objeto criado/atualizado
        """
        if full_path is None and source:
            full_path = os.path.join(source, filename)
        elif full_path is None:
            full_path = filename
        session = self.get_session()
        try:
            ufdr_file = session.query(UFDRFile).filter_by(id=ufdr_id).first()

            if ufdr_file:
                ufdr_file.filename = filename
                ufdr_file.source = source
                ufdr_file.full_path = full_path
                ufdr_file.extraction_type = extraction_type
                ufdr_file.cellebrite_version = cellebrite_version
                ufdr_file.status = status
                ufdr_file.processed_at = datetime.now(timezone.utc)
            else:
                ufdr_file = UFDRFile(
                    id=ufdr_id,
                    filename=filename,
                    source=source,
                    full_path=full_path,
                    extraction_type=extraction_type,
                    cellebrite_version=cellebrite_version,
                    status=status
                )
                session.add(ufdr_file)

            session.commit()
            return type('UFDRFileData', (), {
                'id': ufdr_file.id,
                'filename': ufdr_file.filename,
                'source': ufdr_file.source,
                'full_path': ufdr_file.full_path,
                'extraction_type': ufdr_file.extraction_type,
                'cellebrite_version': ufdr_file.cellebrite_version,
                'status': ufdr_file.status,
                'processed_at': ufdr_file.processed_at
            })()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao adicionar UFDR file: {e}")
            raise
        finally:
            session.close()
    
    def batch_insert_text_entries(
        self,
        entries: List[Tuple[str, str, Optional[str], Optional[str], Optional[str], Optional[str]]]
    ) -> int:
        """
        Insere múltiplas entradas de texto em batch.

        Args:
            entries: Lista de tuplas (ufdr_id, content, source_path, source_name, full_source_path, file_md5)

        Returns:
            int: Número de entradas inseridas
        """
        if not entries:
            return 0

        session = self.get_session()
        try:
            text_entries = [
                TextEntry(
                    ufdr_id=ufdr_id,
                    content=content,
                    source_path=source_path,
                    source_name=source_name,
                    full_source_path=full_source_path,
                    file_md5=file_md5
                )
                for ufdr_id, content, source_path, source_name, full_source_path, file_md5 in entries
            ]
            
            # Usa add_all que permite autoincrement funcionar corretamente
            session.add_all(text_entries)
            # Flush para garantir que os IDs sejam gerados antes do commit
            session.flush()
            session.commit()
            return len(text_entries)
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao inserir text entries em batch: {e}")
            raise
        finally:
            session.close()
    
    def batch_insert_regex_hits(
        self,
        hits: List[Tuple[str, str, str, bool, Optional[str], Optional[str], Optional[str]]]
    ) -> int:
        """
        Insere múltiplos regex hits em batch.

        Args:
            hits: Lista de tuplas (ufdr_id, type, value, validated, context, source_path, file_md5)

        Returns:
            int: Número de hits inseridos
        """
        if not hits:
            return 0

        session = self.get_session()
        try:
            regex_hits = [
                RegexHit(
                    ufdr_id=ufdr_id,
                    type=type_name,
                    value=value,
                    validated=validated,
                    context=context,
                    source_path=source_path,
                    file_md5=file_md5
                )
                for ufdr_id, type_name, value, validated, context, source_path, file_md5 in hits
            ]
            
            # Usa add_all que permite autoincrement funcionar corretamente
            session.add_all(regex_hits)
            # Flush para garantir que os IDs sejam gerados antes do commit
            session.flush()
            session.commit()
            return len(regex_hits)
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao inserir regex hits em batch: {e}")
            raise
        finally:
            session.close()
    
    def is_ufdr_processed(self, ufdr_id: str) -> bool:
        """
        Verifica se um UFDR já foi processado.
        
        Args:
            ufdr_id: Hash SHA-256 do arquivo
        
        Returns:
            bool: True se já foi processado
        """
        session = self.get_session()
        try:
            count = session.query(UFDRFile).filter_by(id=ufdr_id).count()
            return count > 0
        finally:
            session.close()
    
    def get_all_ufdr_files(self) -> List[UFDRFile]:
        """Retorna todos os arquivos UFDR processados"""
        session = self.get_session()
        try:
            # Expira qualquer cache e força refresh
            session.expire_all()
            results = session.query(UFDRFile).order_by(UFDRFile.processed_at.desc()).all()
            # Força refresh dos objetos para garantir dados atualizados
            for ufdr in results:
                session.refresh(ufdr)
            return results
        finally:
            session.close()

    def batch_insert_location_points(
        self,
        ufdr_id: str,
        points: List[Tuple[float, float, Optional[datetime]]],
        source_path: Optional[str] = None,
    ) -> int:
        """
        Insere pontos de histórico de localização para um UFDR.

        Args:
            ufdr_id: ID do UFDR
            points: Lista de (latitude, longitude, point_at datetime ou None)
            source_path: Caminho do arquivo de origem no UFDR (opcional)

        Returns:
            Número de pontos inseridos
        """
        if not points:
            return 0
        session = self.get_session()
        try:
            objs = [
                LocationPoint(
                    ufdr_id=ufdr_id,
                    latitude=lat,
                    longitude=lon,
                    point_at=pt_at,
                    source_path=source_path,
                )
                for lat, lon, pt_at in points
            ]
            session.add_all(objs)
            session.flush()
            session.commit()
            return len(objs)
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Erro ao inserir location points: %s", e)
            raise
        finally:
            session.close()

    def get_location_points(
        self, ufdr_id: str
    ) -> List[Tuple[float, float, Optional[datetime]]]:
        """Retorna (lat, lon, point_at) para todos os pontos de um UFDR."""
        session = self.get_session()
        try:
            rows = (
                session.query(LocationPoint.latitude, LocationPoint.longitude, LocationPoint.point_at)
                .filter(LocationPoint.ufdr_id == ufdr_id)
                .order_by(LocationPoint.point_at.asc().nulls_last(), LocationPoint.id.asc())
                .all()
            )
            return [(r[0], r[1], r[2]) for r in rows]
        finally:
            session.close()

    def get_ufdr_ids_with_locations(self) -> List[Tuple[str, int]]:
        """Retorna [(ufdr_id, count)] dos UFDRs que possuem pontos de localização."""
        session = self.get_session()
        try:
            from sqlalchemy import func

            rows = (
                session.query(LocationPoint.ufdr_id, func.count(LocationPoint.id))
                .group_by(LocationPoint.ufdr_id)
                .all()
            )
            return [(r[0], r[1]) for r in rows]
        finally:
            session.close()


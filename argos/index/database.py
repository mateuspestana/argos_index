"""
Camada de persistência - Gerencia banco de dados SQLite ou MySQL
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import (
    Boolean, BigInteger, CHAR, Column, DateTime, ForeignKey,
    Index, Integer, String, Text, create_engine
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
    processed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), comment="Timestamp de processamento")
    status = Column(String(20), nullable=False, default="processed", comment="Status: processed, error")
    
    # Relacionamentos
    text_entries = relationship("TextEntry", back_populates="ufdr_file", cascade="all, delete-orphan")
    regex_hits = relationship("RegexHit", back_populates="ufdr_file", cascade="all, delete-orphan")


class TextEntry(Base):
    """Tabela de entradas de texto extraídas"""
    __tablename__ = "text_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ufdr_id = Column(CHAR(64), ForeignKey("ufdr_files.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False, comment="Texto bruto extraído")
    source_path = Column(Text, nullable=True, comment="Caminho interno no UFDR")
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
        """Cria todas as tabelas do schema se não existirem"""
        try:
            Base.metadata.create_all(self.engine, checkfirst=True)
            logger.info("Tabelas verificadas/criadas com sucesso")
        except SQLAlchemyError as e:
            logger.error(f"Erro ao criar tabelas: {e}")
            raise
    
    def get_session(self) -> Session:
        """Retorna uma nova sessão do banco de dados"""
        return self.SessionLocal()
    
    def add_ufdr_file(
        self,
        ufdr_id: str,
        filename: str,
        source: Optional[str] = None,
        status: str = "processed"
    ) -> UFDRFile:
        """
        Adiciona ou atualiza um arquivo UFDR.
        
        Args:
            ufdr_id: Hash SHA-256 do arquivo
            filename: Nome do arquivo
            source: Origem do arquivo
            status: Status (processed, error)
        
        Returns:
            UFDRFile: Objeto criado/atualizado
        """
        session = self.get_session()
        try:
            ufdr_file = session.query(UFDRFile).filter_by(id=ufdr_id).first()
            
            if ufdr_file:
                ufdr_file.filename = filename
                ufdr_file.source = source
                ufdr_file.status = status
                ufdr_file.processed_at = datetime.now(timezone.utc)
            else:
                ufdr_file = UFDRFile(
                    id=ufdr_id,
                    filename=filename,
                    source=source,
                    status=status
                )
                session.add(ufdr_file)
            
            session.commit()
            # Retorna uma cópia dos dados para evitar DetachedInstanceError
            # O objeto original fica na sessão que será fechada
            return type('UFDRFileData', (), {
                'id': ufdr_file.id,
                'filename': ufdr_file.filename,
                'source': ufdr_file.source,
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
        entries: List[Tuple[str, str, Optional[str]]]
    ) -> int:
        """
        Insere múltiplas entradas de texto em batch.
        
        Args:
            entries: Lista de tuplas (ufdr_id, content, source_path)
        
        Returns:
            int: Número de entradas inseridas
        """
        if not entries:
            return 0
        
        session = self.get_session()
        try:
            # Cria objetos TextEntry - SQLAlchemy gerará IDs automaticamente
            text_entries = [
                TextEntry(
                    ufdr_id=ufdr_id,
                    content=content,
                    source_path=source_path
                )
                for ufdr_id, content, source_path in entries
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
        hits: List[Tuple[str, str, str, bool, Optional[str]]]
    ) -> int:
        """
        Insere múltiplos regex hits em batch.
        
        Args:
            hits: Lista de tuplas (ufdr_id, type, value, validated, context)
        
        Returns:
            int: Número de hits inseridos
        """
        if not hits:
            return 0
        
        session = self.get_session()
        try:
            # Cria objetos RegexHit - SQLAlchemy gerará IDs automaticamente
            regex_hits = [
                RegexHit(
                    ufdr_id=ufdr_id,
                    type=type_name,
                    value=value,
                    validated=validated,
                    context=context
                )
                for ufdr_id, type_name, value, validated, context in hits
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


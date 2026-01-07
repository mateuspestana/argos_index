"""
Extrator de arquivos UFDR - Trata UFDR como ZIP e extrai conteúdo
"""

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from argos.config import TEMP_DIR
from argos.utils.hashing import calculate_file_hash

logger = logging.getLogger(__name__)


class UFDRExtractor:
    """Extrator de arquivos UFDR"""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        """
        Inicializa o extrator.
        
        Args:
            temp_dir: Diretório temporário para extração (padrão: config.TEMP_DIR)
        """
        self.temp_dir = temp_dir or TEMP_DIR
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    def extract(self, ufdr_path: Path, ufdr_id: str) -> Path:
        """
        Extrai um arquivo UFDR para diretório temporário.
        
        Args:
            ufdr_path: Caminho para o arquivo .ufdr
            ufdr_id: ID único do UFDR (hash SHA-256)
        
        Returns:
            Path: Caminho do diretório de extração
        """
        extract_dir = self.temp_dir / ufdr_id
        
        # Remove diretório anterior se existir
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Tenta abrir como ZIP
            with zipfile.ZipFile(ufdr_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            logger.info(f"UFDR extraído: {ufdr_path.name} -> {extract_dir}")
            return extract_dir
        
        except zipfile.BadZipFile:
            logger.error(f"Arquivo não é um ZIP válido: {ufdr_path}")
            raise ValueError(f"Arquivo UFDR inválido: {ufdr_path}")
        except Exception as e:
            logger.error(f"Erro ao extrair UFDR {ufdr_path}: {e}")
            # Limpa diretório em caso de erro
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            raise
    
    def find_database(self, extract_dir: Path) -> Optional[Path]:
        """
        Procura por database.db no diretório extraído.
        
        Procura em:
        - database.db (raiz)
        - DbData/database.db
        
        Args:
            extract_dir: Diretório de extração
        
        Returns:
            Path: Caminho do database.db se encontrado, None caso contrário
        """
        # Procura na raiz
        db_path = extract_dir / "database.db"
        if db_path.exists():
            return db_path
        
        # Procura em DbData/
        db_path = extract_dir / "DbData" / "database.db"
        if db_path.exists():
            return db_path
        
        return None
    
    def cleanup(self, extract_dir: Path):
        """
        Remove diretório de extração.
        
        Args:
            extract_dir: Diretório a ser removido
        """
        try:
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
                logger.debug(f"Diretório de extração removido: {extract_dir}")
        except Exception as e:
            logger.warning(f"Erro ao limpar diretório {extract_dir}: {e}")
    
    @staticmethod
    def get_ufdr_id(ufdr_path: Path) -> str:
        """
        Calcula o ID único (hash SHA-256) de um arquivo UFDR.
        
        Args:
            ufdr_path: Caminho para o arquivo .ufdr
        
        Returns:
            str: Hash SHA-256 em hexadecimal
        """
        return calculate_file_hash(ufdr_path)


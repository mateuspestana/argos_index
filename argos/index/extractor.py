"""
Extrator de arquivos UFDR - Trata UFDR como ZIP e extrai conteúdo
"""

import logging
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from argos.config import TEMP_DIR, PERMISSION_DENIED_RETRIES, RETRY_DELAYS
from argos.utils.hashing import calculate_file_hash

logger = logging.getLogger(__name__)


def _is_permission_denied(exc: BaseException) -> bool:
    """Verifica se a exceção é permission denied (EACCES/EPERM)."""
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (13, 1):
        return True
    return False


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

        last_error = None
        delays = RETRY_DELAYS[:PERMISSION_DENIED_RETRIES]
        for attempt in range(PERMISSION_DENIED_RETRIES):
            try:
                with zipfile.ZipFile(ufdr_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                logger.info(f"UFDR extraído: {ufdr_path.name} -> {extract_dir}")
                return extract_dir
            except zipfile.BadZipFile:
                logger.error(f"Arquivo não é um ZIP válido: {ufdr_path}")
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                raise ValueError(f"Arquivo UFDR inválido: {ufdr_path}")
            except (OSError, PermissionError) as e:
                last_error = e
                if _is_permission_denied(e) and attempt < PERMISSION_DENIED_RETRIES - 1:
                    delay = delays[attempt] if attempt < len(delays) else delays[-1]
                    logger.warning(
                        "Permission denied ao abrir UFDR %s (tentativa %d/%d), aguardando %ds: %s",
                        ufdr_path, attempt + 1, PERMISSION_DENIED_RETRIES, delay, e
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Erro ao extrair UFDR {ufdr_path}: {e}")
                    if extract_dir.exists():
                        shutil.rmtree(extract_dir)
                    raise
            except Exception as e:
                logger.error(f"Erro ao extrair UFDR {ufdr_path}: {e}")
                if extract_dir.exists():
                    shutil.rmtree(extract_dir)
                raise
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        raise last_error
    
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


"""
Utilitários para cálculo de hash SHA-256
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Union

from argos.config import PERMISSION_DENIED_RETRIES, RETRY_DELAYS

logger = logging.getLogger(__name__)


def _is_permission_denied(exc: BaseException) -> bool:
    """Verifica se a exceção é permission denied (EACCES/EPERM)."""
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (13, 1):  # EACCES, EPERM
        return True
    if isinstance(exc, IOError) and getattr(exc, "errno", None) in (13, 1):
        return True
    return False


def calculate_file_hash(file_path: Union[str, Path], chunk_size: int = 8192) -> str:
    """
    Calcula o hash SHA-256 de um arquivo.
    Em caso de permission denied, faz retry com backoff até PERMISSION_DENIED_RETRIES.

    Args:
        file_path: Caminho para o arquivo
        chunk_size: Tamanho do chunk para leitura (padrão: 8KB)

    Returns:
        str: Hash SHA-256 em hexadecimal (64 caracteres)

    Raises:
        FileNotFoundError: Se o arquivo não existir
        IOError: Se houver erro ao ler o arquivo após todos os retries
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    last_error = None
    delays = RETRY_DELAYS[:PERMISSION_DENIED_RETRIES]
    for attempt in range(PERMISSION_DENIED_RETRIES):
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except (IOError, OSError, PermissionError) as e:
            last_error = e
            if _is_permission_denied(e) and attempt < PERMISSION_DENIED_RETRIES - 1:
                delay = delays[attempt] if attempt < len(delays) else delays[-1]
                logger.warning(
                    "Permission denied ao ler %s (tentativa %d/%d), aguardando %ds: %s",
                    file_path, attempt + 1, PERMISSION_DENIED_RETRIES, delay, e
                )
                time.sleep(delay)
            else:
                raise IOError(f"Erro ao ler arquivo {file_path}: {e}") from e
    raise IOError(f"Erro ao ler arquivo {file_path}: {last_error}") from last_error


def calculate_file_md5(file_path: Union[str, Path], chunk_size: int = 8192) -> str:
    """
    Calcula o hash MD5 de um arquivo.
    Em caso de permission denied, faz retry com backoff até PERMISSION_DENIED_RETRIES.

    Args:
        file_path: Caminho para o arquivo
        chunk_size: Tamanho do chunk para leitura (padrão: 8KB)

    Returns:
        str: Hash MD5 em hexadecimal (32 caracteres)

    Raises:
        FileNotFoundError: Se o arquivo não existir
        IOError: Se houver erro ao ler o arquivo após todos os retries
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    last_error = None
    delays = RETRY_DELAYS[:PERMISSION_DENIED_RETRIES]
    for attempt in range(PERMISSION_DENIED_RETRIES):
        try:
            md5_hash = hashlib.md5()
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except (IOError, OSError, PermissionError) as e:
            last_error = e
            if _is_permission_denied(e) and attempt < PERMISSION_DENIED_RETRIES - 1:
                delay = delays[attempt] if attempt < len(delays) else delays[-1]
                logger.warning(
                    "Permission denied ao ler %s para MD5 (tentativa %d/%d), aguardando %ds: %s",
                    file_path, attempt + 1, PERMISSION_DENIED_RETRIES, delay, e
                )
                time.sleep(delay)
            else:
                raise IOError(f"Erro ao ler arquivo {file_path}: {e}") from e
    raise IOError(f"Erro ao ler arquivo {file_path}: {last_error}") from last_error


def calculate_string_hash(text: str) -> str:
    """
    Calcula o hash SHA-256 de uma string.
    
    Args:
        text: String para calcular hash
    
    Returns:
        str: Hash SHA-256 em hexadecimal (64 caracteres)
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


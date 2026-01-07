"""
Utilitários para cálculo de hash SHA-256
"""

import hashlib
from pathlib import Path
from typing import Union


def calculate_file_hash(file_path: Union[str, Path], chunk_size: int = 8192) -> str:
    """
    Calcula o hash SHA-256 de um arquivo.
    
    Args:
        file_path: Caminho para o arquivo
        chunk_size: Tamanho do chunk para leitura (padrão: 8KB)
    
    Returns:
        str: Hash SHA-256 em hexadecimal (64 caracteres)
    
    Raises:
        FileNotFoundError: Se o arquivo não existir
        IOError: Se houver erro ao ler o arquivo
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
    
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, "rb") as f:
            # Lê o arquivo em chunks para economizar memória
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)
    except IOError as e:
        raise IOError(f"Erro ao ler arquivo {file_path}: {e}")
    
    return sha256_hash.hexdigest()


def calculate_string_hash(text: str) -> str:
    """
    Calcula o hash SHA-256 de uma string.
    
    Args:
        text: String para calcular hash
    
    Returns:
        str: Hash SHA-256 em hexadecimal (64 caracteres)
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


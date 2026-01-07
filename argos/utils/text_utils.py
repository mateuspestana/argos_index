"""
Utilitários para normalização e processamento de texto
"""

import re
from typing import Optional


def normalize_text(text: bytes, encoding: str = "utf-8") -> str:
    """
    Normaliza texto para UTF-8, removendo null bytes e caracteres inválidos.
    
    Args:
        text: Texto em bytes
        encoding: Encoding a ser usado (padrão: utf-8)
    
    Returns:
        str: Texto normalizado em UTF-8
    """
    if isinstance(text, str):
        # Se já é string, converte para bytes primeiro
        text = text.encode('utf-8', errors='ignore')
    
    # Remove null bytes
    text = text.replace(b'\x00', b'')
    
    # Tenta decodificar com o encoding especificado
    try:
        decoded = text.decode(encoding, errors='ignore')
    except (UnicodeDecodeError, LookupError):
        # Fallback para latin-1 (aceita qualquer byte)
        decoded = text.decode('latin-1', errors='ignore')
    
    # Remove caracteres de controle (exceto quebras de linha e tabs)
    decoded = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', decoded)
    
    # Normaliza espaços em branco múltiplos
    decoded = re.sub(r'\s+', ' ', decoded)
    
    return decoded.strip()


def clean_text(text: str) -> str:
    """
    Limpa e normaliza uma string de texto.
    
    Args:
        text: Texto para limpar
    
    Returns:
        str: Texto limpo
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove caracteres de controle
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normaliza espaços
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_context(text: str, position: int, context_length: int = 100) -> str:
    """
    Extrai contexto ao redor de uma posição no texto.
    
    Args:
        text: Texto completo
        position: Posição no texto
        context_length: Tamanho do contexto em cada lado
    
    Returns:
        str: Contexto extraído
    """
    start = max(0, position - context_length)
    end = min(len(text), position + context_length)
    return text[start:end]


def is_text_file(file_path: str) -> bool:
    """
    Verifica se um arquivo é provavelmente um arquivo de texto.
    
    Args:
        file_path: Caminho do arquivo
    
    Returns:
        bool: True se for arquivo de texto
    """
    text_extensions = {
        '.txt', '.log', '.json', '.xml', '.csv', '.eml', '.html',
        '.htm', '.md', '.py', '.js', '.css', '.sql', '.sh', '.bat'
    }
    
    return any(file_path.lower().endswith(ext) for ext in text_extensions)


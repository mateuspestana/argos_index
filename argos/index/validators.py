"""
Validadores para documentos brasileiros (CPF, CNPJ, CNH)
"""

import re
from typing import Optional


def clean_document(doc: str) -> str:
    """
    Remove caracteres não numéricos de um documento.
    
    Args:
        doc: Documento com ou sem formatação
    
    Returns:
        str: Documento apenas com números
    """
    return re.sub(r'\D', '', doc)


def validate_cpf(cpf: str) -> bool:
    """
    Valida CPF usando algoritmo de dígito verificador.
    
    Args:
        cpf: CPF com ou sem formatação (ex: 123.456.789-00 ou 12345678900)
    
    Returns:
        bool: True se o CPF for válido
    """
    # Remove formatação
    cpf = clean_document(cpf)
    
    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais (CPF inválido)
    if len(set(cpf)) == 1:
        return False
    
    # Valida primeiro dígito verificador
    sum_val = 0
    for i in range(9):
        sum_val += int(cpf[i]) * (10 - i)
    
    remainder = sum_val % 11
    first_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cpf[9]) != first_digit:
        return False
    
    # Valida segundo dígito verificador
    sum_val = 0
    for i in range(10):
        sum_val += int(cpf[i]) * (11 - i)
    
    remainder = sum_val % 11
    second_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cpf[10]) != second_digit:
        return False
    
    return True


def validate_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ usando algoritmo de dígito verificador.
    
    Args:
        cnpj: CNPJ com ou sem formatação (ex: 12.345.678/0001-90 ou 12345678000190)
    
    Returns:
        bool: True se o CNPJ for válido
    """
    # Remove formatação
    cnpj = clean_document(cnpj)
    
    # Verifica se tem 14 dígitos
    if len(cnpj) != 14:
        return False
    
    # Verifica se todos os dígitos são iguais (CNPJ inválido)
    if len(set(cnpj)) == 1:
        return False
    
    # Valida primeiro dígito verificador
    weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_val = sum(int(cnpj[i]) * weights[i] for i in range(12))
    remainder = sum_val % 11
    first_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cnpj[12]) != first_digit:
        return False
    
    # Valida segundo dígito verificador
    weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum_val = sum(int(cnpj[i]) * weights[i] for i in range(13))
    remainder = sum_val % 11
    second_digit = 0 if remainder < 2 else 11 - remainder
    
    if int(cnpj[13]) != second_digit:
        return False
    
    return True


def validate_cnh(cnh: str) -> bool:
    """
    Valida CNH (Carteira Nacional de Habilitação).
    
    Nota: CNH tem formato similar ao CPF mas algoritmo diferente.
    Por enquanto, valida apenas formato básico (11 dígitos).
    
    Args:
        cnh: CNH com ou sem formatação
    
    Returns:
        bool: True se o formato for válido
    """
    # Remove formatação
    cnh = clean_document(cnh)
    
    # CNH deve ter 11 dígitos
    if len(cnh) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais (CNH inválida)
    if len(set(cnh)) == 1:
        return False
    
    # Validação básica de CNH (algoritmo simplificado)
    # CNH válida não pode ter todos os dígitos iguais
    # e deve passar por verificação de soma ponderada
    
    try:
        # Calcula soma ponderada
        sum_val = 0
        for i in range(9):
            sum_val += int(cnh[i]) * (9 - i)
        
        # Calcula primeiro dígito verificador
        remainder = sum_val % 11
        if remainder >= 10:
            first_digit = 0
        else:
            first_digit = remainder
        
        if int(cnh[9]) != first_digit:
            return False
        
        # Calcula segundo dígito verificador
        sum_val = 0
        for i in range(9):
            sum_val += int(cnh[i]) * (1 + i)
        
        remainder = sum_val % 11
        if remainder >= 10:
            second_digit = 0
        else:
            second_digit = remainder
        
        if int(cnh[10]) != second_digit:
            return False
        
        return True
    except (ValueError, IndexError):
        return False


def validate_document(doc_type: str, value: str) -> bool:
    """
    Valida um documento baseado no tipo.
    
    Args:
        doc_type: Tipo do documento (BR_CPF, BR_CNPJ, BR_CNH)
        value: Valor do documento
    
    Returns:
        bool: True se válido, False caso contrário
    """
    if not value:
        return False
    
    doc_type = doc_type.upper()
    
    if doc_type == "BR_CPF":
        return validate_cpf(value)
    elif doc_type == "BR_CNPJ":
        return validate_cnpj(value)
    elif doc_type == "BR_CNH":
        return validate_cnh(value)
    else:
        # Tipos não suportados retornam False
        return False


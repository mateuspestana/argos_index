"""
Testes para módulo utils
"""

import unittest
from pathlib import Path
import tempfile
import os

from argos.utils.hashing import calculate_file_hash, calculate_file_md5, calculate_string_hash
from argos.utils.text_utils import normalize_text, clean_text, extract_context, is_text_file


class TestHashing(unittest.TestCase):
    """Testes para funções de hash"""
    
    def test_calculate_string_hash(self):
        """Testa cálculo de hash de string"""
        text = "teste"
        hash1 = calculate_string_hash(text)
        hash2 = calculate_string_hash(text)
        
        # Deve ser determinístico
        self.assertEqual(hash1, hash2)
        # Deve ter 64 caracteres (SHA-256 hex)
        self.assertEqual(len(hash1), 64)
    
    def test_calculate_file_hash(self):
        """Testa cálculo de hash de arquivo"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("conteudo de teste")
            temp_path = Path(f.name)
        
        try:
            hash1 = calculate_file_hash(temp_path)
            hash2 = calculate_file_hash(temp_path)
            
            # Deve ser determinístico
            self.assertEqual(hash1, hash2)
            # Deve ter 64 caracteres
            self.assertEqual(len(hash1), 64)
        finally:
            os.unlink(temp_path)
    
    def test_calculate_file_hash_nonexistent(self):
        """Testa erro com arquivo inexistente"""
        fake_path = Path("/arquivo/que/nao/existe.txt")
        with self.assertRaises(FileNotFoundError):
            calculate_file_hash(fake_path)
    
    def test_calculate_file_md5(self):
        """Testa cálculo de hash MD5 de arquivo"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("conteudo de teste para md5")
            temp_path = Path(f.name)
        
        try:
            md5_1 = calculate_file_md5(temp_path)
            md5_2 = calculate_file_md5(temp_path)
            
            self.assertEqual(md5_1, md5_2)
            self.assertEqual(len(md5_1), 32)
            # Deve ser hexadecimal válido
            int(md5_1, 16)
        finally:
            os.unlink(temp_path)
    
    def test_calculate_file_md5_nonexistent(self):
        """Testa erro MD5 com arquivo inexistente"""
        fake_path = Path("/arquivo/que/nao/existe.txt")
        with self.assertRaises(FileNotFoundError):
            calculate_file_md5(fake_path)


class TestTextUtils(unittest.TestCase):
    """Testes para utilitários de texto"""
    
    def test_normalize_text(self):
        """Testa normalização de texto"""
        # Texto com null bytes
        text_bytes = b"teste\x00texto\x00normal"
        normalized = normalize_text(text_bytes)
        
        self.assertNotIn('\x00', normalized)
        self.assertIn('teste', normalized)
        self.assertIn('texto', normalized)
    
    def test_clean_text(self):
        """Testa limpeza de texto"""
        text = "  teste   com   espaços  \x00"
        cleaned = clean_text(text)
        
        self.assertNotIn('\x00', cleaned)
        self.assertNotIn('  ', cleaned)  # Não deve ter espaços múltiplos
    
    def test_extract_context(self):
        """Testa extração de contexto"""
        text = "Este é um texto de teste para extrair contexto"
        position = 10
        context = extract_context(text, position, context_length=5)
        
        self.assertIn(text[position], context)
        self.assertLessEqual(len(context), len(text))
    
    def test_is_text_file(self):
        """Testa detecção de arquivo texto"""
        self.assertTrue(is_text_file("arquivo.txt"))
        self.assertTrue(is_text_file("arquivo.json"))
        self.assertTrue(is_text_file("arquivo.xml"))
        self.assertFalse(is_text_file("arquivo.jpg"))
        self.assertFalse(is_text_file("arquivo.exe"))


if __name__ == '__main__':
    unittest.main()


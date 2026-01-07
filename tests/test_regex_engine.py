"""
Testes para motor de regex
"""

import unittest
import json
import tempfile
from pathlib import Path

from argos.index.regex_engine import RegexEngine


class TestRegexEngine(unittest.TestCase):
    """Testes para motor de regex"""
    
    def setUp(self):
        """Cria arquivo de padrões temporário"""
        self.temp_patterns = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        
        # Padrões de teste simples
        patterns_data = {
            "formatRegexMatches": False,
            "patterns": [
                {
                    "name": "EMAIL",
                    "regex": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                    "ignoreCase": True,
                    "prefix": 0,
                    "suffix": 0
                },
                {
                    "name": "TEST_NUMBER",
                    "regex": r"\d{3,}",
                    "ignoreCase": False,
                    "prefix": 0,
                    "suffix": 0
                }
            ]
        }
        
        json.dump(patterns_data, self.temp_patterns)
        self.temp_patterns.close()
        self.patterns_file = Path(self.temp_patterns.name)
    
    def tearDown(self):
        """Remove arquivo temporário"""
        import os
        if os.path.exists(self.temp_patterns.name):
            os.unlink(self.temp_patterns.name)
    
    def test_load_patterns(self):
        """Testa carregamento de padrões"""
        engine = RegexEngine(patterns_file=self.patterns_file)
        
        self.assertGreater(len(engine.patterns), 0)
        self.assertGreater(len(engine.compiled_patterns), 0)
    
    def test_process_text(self):
        """Testa processamento de texto"""
        engine = RegexEngine(patterns_file=self.patterns_file)
        
        text = "Contato: teste@example.com ou 123456789"
        hits = engine.process_text(text, "test_ufdr_id")
        
        # Deve encontrar email e número
        self.assertGreater(len(hits), 0)
        
        # Verifica tipos encontrados
        types_found = [h[0] for h in hits]
        self.assertIn("EMAIL", types_found)
    
    def test_get_pattern_names(self):
        """Testa obtenção de nomes de padrões"""
        engine = RegexEngine(patterns_file=self.patterns_file)
        names = engine.get_pattern_names()
        
        self.assertIn("EMAIL", names)
        self.assertIn("TEST_NUMBER", names)
    
    def test_get_pattern_by_name(self):
        """Testa obtenção de padrão por nome"""
        engine = RegexEngine(patterns_file=self.patterns_file)
        
        pattern = engine.get_pattern_by_name("EMAIL")
        self.assertIsNotNone(pattern)
        self.assertEqual(pattern['name'], "EMAIL")
        
        # Padrão inexistente
        pattern = engine.get_pattern_by_name("NONEXISTENT")
        self.assertIsNone(pattern)


if __name__ == '__main__':
    unittest.main()


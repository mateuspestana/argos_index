"""
Testes de integração - Pipeline completo
"""

import unittest
import tempfile
import zipfile
from pathlib import Path

from argos.index.database import DatabaseManager, TextEntry, RegexHit
from argos.index.extractor import UFDRExtractor
from argos.index.text_extractor import TextExtractor
from argos.index.regex_engine import RegexEngine
import json


class TestIntegration(unittest.TestCase):
    """Testes de integração do pipeline"""
    
    def setUp(self):
        """Configura ambiente de teste"""
        # Banco temporário
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = f"sqlite:///{self.temp_db.name}"
        self.db_manager = DatabaseManager(database_url=self.db_path)
        self.db_manager.create_tables()
        
        # Diretório temporário
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Cria UFDR de teste
        self.ufdr_file = self.temp_dir / "test.ufdr"
        with zipfile.ZipFile(self.ufdr_file, 'w') as zf:
            zf.writestr("files/Text/test.txt", "Email: teste@example.com CPF: 12345678909")
            zf.writestr("files/Text/test2.txt", "Outro texto com número 123456")
        
        # Padrões de teste
        self.patterns_file = self.temp_dir / "patterns.json"
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
                    "name": "BR_CPF",
                    "regex": r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}",
                    "ignoreCase": False,
                    "prefix": 0,
                    "suffix": 0
                }
            ]
        }
        with open(self.patterns_file, 'w') as f:
            json.dump(patterns_data, f)
    
    def tearDown(self):
        """Limpa arquivos temporários"""
        import os
        import shutil
        
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_full_pipeline(self):
        """Testa pipeline completo: extração -> texto -> regex -> banco"""
        # 1. Extrai UFDR
        extractor = UFDRExtractor(temp_dir=self.temp_dir / "extract")
        ufdr_id = extractor.get_ufdr_id(self.ufdr_file)
        extract_dir = extractor.extract(self.ufdr_file, ufdr_id)
        
        try:
            # 2. Extrai texto
            text_extractor = TextExtractor(extract_dir)
            extracted_texts = list(text_extractor.extract_all())
            
            self.assertGreater(len(extracted_texts), 0)
            
            # 3. Processa regex
            regex_engine = RegexEngine(patterns_file=self.patterns_file)
            all_hits = []
            
            for text, source_path in extracted_texts:
                hits = regex_engine.process_text(text, ufdr_id)
                for type_name, value, validated, context in hits:
                    all_hits.append((ufdr_id, type_name, value, validated, context))
            
            self.assertGreater(len(all_hits), 0)
            
            # 4. Persiste no banco
            self.db_manager.add_ufdr_file(ufdr_id, self.ufdr_file.name)
            
            # Prepara text_entries no formato correto: (ufdr_id, content, source_path)
            text_entries = [(ufdr_id, text, source_path) for text, source_path in extracted_texts]
            self.db_manager.batch_insert_text_entries(text_entries)
            self.db_manager.batch_insert_regex_hits(all_hits)
            
            # 5. Verifica persistência
            self.assertTrue(self.db_manager.is_ufdr_processed(ufdr_id))
            
            session = self.db_manager.get_session()
            try:
                text_count = session.query(TextEntry).filter_by(ufdr_id=ufdr_id).count()
                hits_count = session.query(RegexHit).filter_by(ufdr_id=ufdr_id).count()
                
                self.assertGreater(text_count, 0)
                self.assertGreater(hits_count, 0)
            finally:
                session.close()
        
        finally:
            extractor.cleanup(extract_dir)


if __name__ == '__main__':
    unittest.main()


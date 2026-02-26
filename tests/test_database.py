"""
Testes para módulo de banco de dados
"""

import unittest
import tempfile
from pathlib import Path

from argos.index.database import DatabaseManager, UFDRFile, TextEntry, RegexHit


class TestDatabase(unittest.TestCase):
    """Testes para banco de dados"""
    
    def setUp(self):
        """Configura banco de dados temporário para testes"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.db_path = f"sqlite:///{self.temp_db.name}"
        self.db_manager = DatabaseManager(database_url=self.db_path)
        self.db_manager.create_tables()
    
    def tearDown(self):
        """Limpa banco de dados temporário"""
        import os
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_create_tables(self):
        """Testa criação de tabelas"""
        # Tabelas devem ser criadas sem erro
        session = self.db_manager.get_session()
        try:
            # Verifica se tabelas existem tentando fazer query
            ufdr_count = session.query(UFDRFile).count()
            text_count = session.query(TextEntry).count()
            regex_count = session.query(RegexHit).count()
            
            # Se não der erro, tabelas existem
            self.assertIsInstance(ufdr_count, int)
            self.assertIsInstance(text_count, int)
            self.assertIsInstance(regex_count, int)
        finally:
            session.close()
    
    def test_add_ufdr_file(self):
        """Testa adição de arquivo UFDR"""
        ufdr_id = "a" * 64  # Hash simulado
        filename = "teste.ufdr"
        
        ufdr_file = self.db_manager.add_ufdr_file(
            ufdr_id=ufdr_id,
            filename=filename,
            source="/test/path",
            status="processed"
        )
        
        session = self.db_manager.get_session()
        try:
            saved = session.query(UFDRFile).filter_by(id=ufdr_id).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.id, ufdr_id)
            self.assertEqual(saved.filename, filename)
        finally:
            session.close()
    
    def test_add_ufdr_file_with_metadata(self):
        """Testa adição de UFDR com metadados de extração e versão Cellebrite"""
        ufdr_id = "e" * 64
        
        self.db_manager.add_ufdr_file(
            ufdr_id=ufdr_id,
            filename="apple_extract.ufdr",
            source="/test/path",
            extraction_type="Apple",
            cellebrite_version="7.58.0.24",
            status="processed"
        )
        
        session = self.db_manager.get_session()
        try:
            saved = session.query(UFDRFile).filter_by(id=ufdr_id).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.extraction_type, "Apple")
            self.assertEqual(saved.cellebrite_version, "7.58.0.24")
        finally:
            session.close()
    
    def test_is_ufdr_processed(self):
        """Testa verificação de UFDR processado"""
        ufdr_id = "b" * 64
        
        # Não deve estar processado
        self.assertFalse(self.db_manager.is_ufdr_processed(ufdr_id))
        
        # Adiciona
        self.db_manager.add_ufdr_file(ufdr_id, "test.ufdr")
        
        # Agora deve estar processado
        self.assertTrue(self.db_manager.is_ufdr_processed(ufdr_id))
    
    def test_batch_insert_text_entries(self):
        """Testa inserção em batch de text entries com file_md5"""
        ufdr_id = "c" * 64
        self.db_manager.add_ufdr_file(ufdr_id, "test.ufdr")
        
        entries = [
            (ufdr_id, "Texto 1", "path1.txt", "path1.txt", "/full/path1.txt", "a" * 32),
            (ufdr_id, "Texto 2", "path2.txt", "path2.txt", "/full/path2.txt", "b" * 32),
            (ufdr_id, "Texto 3", "path3.txt", "path3.txt", "/full/path3.txt", None),
        ]

        count = self.db_manager.batch_insert_text_entries(entries)
        self.assertEqual(count, 3)
        
        session = self.db_manager.get_session()
        try:
            saved = session.query(TextEntry).filter_by(ufdr_id=ufdr_id).all()
            self.assertEqual(len(saved), 3)
            md5s = {e.source_name: e.file_md5 for e in saved}
            self.assertEqual(md5s["path1.txt"], "a" * 32)
            self.assertEqual(md5s["path2.txt"], "b" * 32)
            self.assertIsNone(md5s["path3.txt"])
        finally:
            session.close()
    
    def test_batch_insert_regex_hits(self):
        """Testa inserção em batch de regex hits com file_md5"""
        ufdr_id = "d" * 64
        self.db_manager.add_ufdr_file(ufdr_id, "test.ufdr")
        
        hits = [
            (ufdr_id, "EMAIL", "test@example.com", True, "contexto 1", "path1.txt", "a" * 32),
            (ufdr_id, "BR_CPF", "12345678900", False, "contexto 2", "path2.txt", None),
        ]

        count = self.db_manager.batch_insert_regex_hits(hits)
        self.assertEqual(count, 2)
        
        session = self.db_manager.get_session()
        try:
            saved = session.query(RegexHit).filter_by(ufdr_id=ufdr_id).all()
            self.assertEqual(len(saved), 2)
            md5s = {h.type: h.file_md5 for h in saved}
            self.assertEqual(md5s["EMAIL"], "a" * 32)
            self.assertIsNone(md5s["BR_CPF"])
        finally:
            session.close()


if __name__ == '__main__':
    unittest.main()


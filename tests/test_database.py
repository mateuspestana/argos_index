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
        
        # Acessa atributos antes que a sessão seja fechada (se ainda estiver aberta)
        # Ou verifica diretamente no banco
        session = self.db_manager.get_session()
        try:
            saved = session.query(UFDRFile).filter_by(id=ufdr_id).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.id, ufdr_id)
            self.assertEqual(saved.filename, filename)
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
        """Testa inserção em batch de text entries"""
        ufdr_id = "c" * 64
        self.db_manager.add_ufdr_file(ufdr_id, "test.ufdr")
        
        entries = [
            (ufdr_id, "Texto 1", "path1.txt"),
            (ufdr_id, "Texto 2", "path2.txt"),
            (ufdr_id, "Texto 3", "path3.txt"),
        ]
        
        count = self.db_manager.batch_insert_text_entries(entries)
        self.assertEqual(count, 3)
        
        # Verifica se foram inseridos
        session = self.db_manager.get_session()
        try:
            saved = session.query(TextEntry).filter_by(ufdr_id=ufdr_id).all()
            self.assertEqual(len(saved), 3)
        finally:
            session.close()
    
    def test_batch_insert_regex_hits(self):
        """Testa inserção em batch de regex hits"""
        ufdr_id = "d" * 64
        self.db_manager.add_ufdr_file(ufdr_id, "test.ufdr")
        
        hits = [
            (ufdr_id, "EMAIL", "test@example.com", True, "contexto 1"),
            (ufdr_id, "BR_CPF", "12345678900", False, "contexto 2"),
        ]
        
        count = self.db_manager.batch_insert_regex_hits(hits)
        self.assertEqual(count, 2)
        
        # Verifica se foram inseridos
        session = self.db_manager.get_session()
        try:
            saved = session.query(RegexHit).filter_by(ufdr_id=ufdr_id).all()
            self.assertEqual(len(saved), 2)
        finally:
            session.close()


if __name__ == '__main__':
    unittest.main()


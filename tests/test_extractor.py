"""
Testes para extrator de UFDR
"""

import unittest
import tempfile
import zipfile
from pathlib import Path

from argos.index.extractor import UFDRExtractor


class TestUFDRExtractor(unittest.TestCase):
    """Testes para extrator de UFDR"""
    
    def setUp(self):
        """Cria arquivo ZIP temporário simulando UFDR"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ufdr_file = self.temp_dir / "test.ufdr"
        
        # Cria ZIP simples
        with zipfile.ZipFile(self.ufdr_file, 'w') as zf:
            zf.writestr("test.txt", "conteudo de teste")
            zf.writestr("DbData/database.db", "fake database content")
        
        self.extractor = UFDRExtractor(temp_dir=self.temp_dir / "extract")
    
    def tearDown(self):
        """Limpa arquivos temporários"""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_get_ufdr_id(self):
        """Testa cálculo de ID do UFDR"""
        ufdr_id = UFDRExtractor.get_ufdr_id(self.ufdr_file)
        
        self.assertEqual(len(ufdr_id), 64)  # SHA-256 hex
        # Deve ser determinístico
        ufdr_id2 = UFDRExtractor.get_ufdr_id(self.ufdr_file)
        self.assertEqual(ufdr_id, ufdr_id2)
    
    def test_extract(self):
        """Testa extração de UFDR"""
        ufdr_id = "test_id_" + "a" * 56  # 64 chars total
        extract_dir = self.extractor.extract(self.ufdr_file, ufdr_id)
        
        self.assertTrue(extract_dir.exists())
        # Verifica se arquivos foram extraídos
        self.assertTrue((extract_dir / "test.txt").exists())
        self.assertTrue((extract_dir / "DbData" / "database.db").exists())
    
    def test_find_database(self):
        """Testa localização de database.db"""
        ufdr_id = "test_id_" + "b" * 56
        extract_dir = self.extractor.extract(self.ufdr_file, ufdr_id)
        
        db_path = self.extractor.find_database(extract_dir)
        self.assertIsNotNone(db_path)
        self.assertTrue(db_path.exists())
        self.assertEqual(db_path.name, "database.db")
    
    def test_cleanup(self):
        """Testa limpeza de diretório de extração"""
        ufdr_id = "test_id_" + "c" * 56
        extract_dir = self.extractor.extract(self.ufdr_file, ufdr_id)
        
        self.assertTrue(extract_dir.exists())
        self.extractor.cleanup(extract_dir)
        self.assertFalse(extract_dir.exists())


if __name__ == '__main__':
    unittest.main()


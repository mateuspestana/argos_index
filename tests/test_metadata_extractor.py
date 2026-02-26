"""
Testes para o extrator de metadados de UFDR
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from argos.index.metadata_extractor import UFDRMetadataExtractor, UFDRMetadata


class TestClassifyExtractionType(unittest.TestCase):
    """Testes para classificação de tipo de extração"""

    def test_apple_iphone(self):
        self.assertEqual(UFDRMetadataExtractor._classify_extraction_type("iPhone 12 Pro"), "Apple")

    def test_apple_ipad(self):
        self.assertEqual(UFDRMetadataExtractor._classify_extraction_type("iPad Air"), "Apple")

    def test_apple_ios(self):
        self.assertEqual(UFDRMetadataExtractor._classify_extraction_type("iOS 16.1"), "Apple")

    def test_android_samsung(self):
        self.assertEqual(
            UFDRMetadataExtractor._classify_extraction_type("Samsung Galaxy S21"),
            "Google (Android)",
        )

    def test_android_pixel(self):
        self.assertEqual(
            UFDRMetadataExtractor._classify_extraction_type("Google Pixel 7"),
            "Google (Android)",
        )

    def test_android_keyword(self):
        self.assertEqual(
            UFDRMetadataExtractor._classify_extraction_type("Android 13"),
            "Google (Android)",
        )

    def test_unknown(self):
        self.assertEqual(UFDRMetadataExtractor._classify_extraction_type("Unknown device XYZ"), "Desconhecido")

    def test_empty(self):
        self.assertEqual(UFDRMetadataExtractor._classify_extraction_type(""), "Desconhecido")

    def test_none(self):
        self.assertEqual(UFDRMetadataExtractor._classify_extraction_type(None), "Desconhecido")


class TestExtractVersionFromText(unittest.TestCase):
    """Testes para extração de versão Cellebrite"""

    def test_ufed_version(self):
        text = "UFED 4PC 7.58.0.24 extraction"
        v = UFDRMetadataExtractor._extract_version_from_text(text)
        self.assertEqual(v, "7.58.0.24")

    def test_cellebrite_version(self):
        text = "Cellebrite UFED version 10.0.1"
        v = UFDRMetadataExtractor._extract_version_from_text(text)
        self.assertEqual(v, "10.0.1")

    def test_pa_version(self):
        text = "PA Version: 7.69.0.12"
        v = UFDRMetadataExtractor._extract_version_from_text(text)
        self.assertEqual(v, "7.69.0.12")

    def test_no_version(self):
        text = "No version info here"
        v = UFDRMetadataExtractor._extract_version_from_text(text)
        self.assertIsNone(v)


class TestExtractMetadataFromReportXml(unittest.TestCase):
    """Testes de extração de metadados via report.xml"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_report_xml_apple(self):
        report = self.temp_dir / "report.xml"
        report.write_text(
            '<?xml version="1.0"?>\n'
            '<project>\n'
            '  <extractionInfo>\n'
            '    <deviceModel>iPhone 14 Pro Max</deviceModel>\n'
            '    <UFEDVersion>UFED 4PC 7.58.0.24</UFEDVersion>\n'
            '  </extractionInfo>\n'
            '</project>\n',
            encoding='utf-8',
        )

        extractor = UFDRMetadataExtractor(self.temp_dir)
        metadata = extractor.extract_metadata()

        self.assertEqual(metadata.extraction_type, "Apple")
        self.assertEqual(metadata.cellebrite_version, "7.58.0.24")

    def test_report_xml_android(self):
        report = self.temp_dir / "report.xml"
        report.write_text(
            '<?xml version="1.0"?>\n'
            '<project>\n'
            '  <extractionInfo>\n'
            '    <deviceModel>Samsung Galaxy S23</deviceModel>\n'
            '    <appVersion>Cellebrite UFED 10.0.1</appVersion>\n'
            '  </extractionInfo>\n'
            '</project>\n',
            encoding='utf-8',
        )

        extractor = UFDRMetadataExtractor(self.temp_dir)
        metadata = extractor.extract_metadata()

        self.assertEqual(metadata.extraction_type, "Google (Android)")
        self.assertEqual(metadata.cellebrite_version, "10.0.1")

    def test_empty_dir(self):
        extractor = UFDRMetadataExtractor(self.temp_dir)
        metadata = extractor.extract_metadata()

        self.assertEqual(metadata.extraction_type, "Desconhecido")
        self.assertIsNone(metadata.cellebrite_version)

    def test_directory_structure_fallback(self):
        (self.temp_dir / "Apple_iPhone14").mkdir()
        extractor = UFDRMetadataExtractor(self.temp_dir)
        metadata = extractor.extract_metadata()

        self.assertEqual(metadata.extraction_type, "Apple")


class TestExtractMetadataFromSqlite(unittest.TestCase):
    """Testes de extração de metadados via database.db SQLite"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_sqlite_extraction_infos(self):
        import sqlite3
        db_path = self.temp_dir / "database.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE ExtractionInfos (Id INTEGER PRIMARY KEY, DeviceName TEXT, UfedVersion TEXT)"
        )
        conn.execute(
            "INSERT INTO ExtractionInfos (Id, DeviceName, UfedVersion) VALUES (1, 'iPad Pro', 'UFED 7.60.0.1')"
        )
        conn.commit()
        conn.close()

        extractor = UFDRMetadataExtractor(self.temp_dir)
        metadata = extractor.extract_metadata()

        self.assertEqual(metadata.extraction_type, "Apple")
        self.assertEqual(metadata.cellebrite_version, "7.60.0.1")


if __name__ == '__main__':
    unittest.main()

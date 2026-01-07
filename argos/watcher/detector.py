"""
Detector de novos arquivos UFDR
"""

import logging
from pathlib import Path
from typing import List, Optional

from argos.index.database import DatabaseManager
from argos.index.extractor import UFDRExtractor
from argos.utils.hashing import calculate_file_hash

logger = logging.getLogger(__name__)


class UFDRDetector:
    """Detector de arquivos UFDR novos ou não processados"""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Inicializa o detector.
        
        Args:
            db_manager: Gerenciador de banco de dados
        """
        self.db_manager = db_manager
    
    def detect_new_files(self, directory: Path) -> List[Path]:
        """
        Detecta arquivos UFDR novos no diretório.
        
        Args:
            directory: Diretório para monitorar
        
        Returns:
            Lista de caminhos para arquivos UFDR novos
        """
        if not directory.exists():
            logger.warning(f"Diretório não existe: {directory}")
            return []
        
        new_files = []
        
        # Procura por arquivos .ufdr
        for ufdr_file in directory.glob("*.ufdr"):
            if not ufdr_file.is_file():
                continue
            
            try:
                # Calcula hash do arquivo
                ufdr_id = calculate_file_hash(ufdr_file)
                
                # Verifica se já foi processado
                if not self.db_manager.is_ufdr_processed(ufdr_id):
                    new_files.append(ufdr_file)
                    logger.info(f"Novo arquivo UFDR detectado: {ufdr_file.name}")
                else:
                    logger.debug(f"Arquivo já processado: {ufdr_file.name}")
            
            except Exception as e:
                logger.error(f"Erro ao processar arquivo {ufdr_file}: {e}")
                continue
        
        return new_files
    
    def get_ufdr_id(self, ufdr_path: Path) -> str:
        """
        Calcula o ID único de um arquivo UFDR.
        
        Args:
            ufdr_path: Caminho para o arquivo .ufdr
        
        Returns:
            str: Hash SHA-256 do arquivo
        """
        return calculate_file_hash(ufdr_path)


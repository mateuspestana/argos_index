"""
Monitor de diretórios e URLs para detecção de novos arquivos UFDR
"""

import logging
import time
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from argos.config import WATCH_DIRECTORY, WATCH_URL
from argos.watcher.detector import UFDRDetector
from argos.index.database import DatabaseManager

logger = logging.getLogger(__name__)


class UFDRFileHandler(FileSystemEventHandler):
    """Handler para eventos de arquivos UFDR"""
    
    def __init__(self, detector: UFDRDetector, callback):
        """
        Inicializa o handler.
        
        Args:
            detector: Detector de UFDRs
            callback: Função chamada quando novo arquivo é detectado
        """
        self.detector = detector
        self.callback = callback
        super().__init__()
    
    def on_created(self, event: FileSystemEvent):
        """Chamado quando um arquivo é criado"""
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix.lower() == '.ufdr':
                logger.info(f"Arquivo UFDR criado: {file_path}")
                # Verifica se é novo
                try:
                    ufdr_id = self.detector.get_ufdr_id(file_path)
                    if not self.detector.db_manager.is_ufdr_processed(ufdr_id):
                        self.callback(file_path)
                except Exception as e:
                    logger.error(f"Erro ao processar arquivo criado {file_path}: {e}")


class UFDRMonitor:
    """Monitor de diretórios para arquivos UFDR"""
    
    def __init__(
        self,
        watch_directory: Optional[Path] = None,
        db_manager: Optional[DatabaseManager] = None
    ):
        """
        Inicializa o monitor.
        
        Args:
            watch_directory: Diretório para monitorar (padrão: config.WATCH_DIRECTORY)
            db_manager: Gerenciador de banco de dados
        """
        self.watch_directory = Path(watch_directory or WATCH_DIRECTORY)
        # Garante que é um Path absoluto
        if not self.watch_directory.is_absolute():
            from argos.config import PROJECT_ROOT
            self.watch_directory = PROJECT_ROOT / self.watch_directory
        self.db_manager = db_manager or DatabaseManager()
        self.detector = UFDRDetector(self.db_manager)
        self.observer: Optional[Observer] = None
        self.callback = None
        logger.info(f"UFDRMonitor inicializado. Diretório: {self.watch_directory}")
    
    def start_monitoring(self, callback, continuous: bool = True):
        """
        Inicia monitoramento contínuo do diretório.
        
        Args:
            callback: Função chamada quando novo UFDR é detectado (recebe Path)
            continuous: Se True, monitora continuamente; se False, faz varredura única
        """
        self.callback = callback
        
        if continuous:
            # Modo contínuo com watchdog
            # Primeiro faz scan inicial de arquivos existentes
            logger.info("Fazendo scan inicial de arquivos existentes...")
            self._scan_once(callback)
            
            # Depois inicia monitoramento contínuo
            event_handler = UFDRFileHandler(self.detector, callback)
            self.observer = Observer()
            self.observer.schedule(event_handler, str(self.watch_directory), recursive=False)
            self.observer.start()
            logger.info(f"Monitoramento contínuo iniciado em: {self.watch_directory}")
        else:
            # Varredura única
            self._scan_once(callback)
    
    def _scan_once(self, callback):
        """Faz varredura única do diretório"""
        logger.info(f"Varredura única em: {self.watch_directory}")
        new_files = self.detector.detect_new_files(self.watch_directory)
        
        if new_files:
            logger.info(f"Encontrados {len(new_files)} arquivo(s) novo(s) para processar")
        else:
            logger.info("Nenhum arquivo novo encontrado")
        
        for ufdr_file in new_files:
            try:
                logger.info(f"Processando arquivo existente: {ufdr_file.name}")
                callback(ufdr_file)
            except Exception as e:
                logger.error(f"Erro ao processar {ufdr_file}: {e}")
    
    def stop_monitoring(self):
        """Para o monitoramento"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Monitoramento parado")
    
    def scan(self) -> list:
        """
        Faz varredura única e retorna lista de novos arquivos.
        
        Returns:
            Lista de Paths para novos arquivos UFDR
        """
        return self.detector.detect_new_files(self.watch_directory)


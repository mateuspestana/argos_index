"""
Monitor de diretórios e URLs para detecção de novos arquivos UFDR
"""

import logging
import queue
import threading
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from argos.config import WATCH_DIRECTORY, FILE_STABLE_SECONDS
from argos.watcher.detector import UFDRDetector
from argos.index.database import DatabaseManager
from argos.utils.file_stability import wait_until_stable

logger = logging.getLogger(__name__)


class UFDRFileHandler(FileSystemEventHandler):
    """Handler para eventos de arquivos UFDR. Coloca paths na fila (não abre o arquivo)."""

    def __init__(self, pending_queue: queue.Queue):
        """
        Inicializa o handler.

        Args:
            pending_queue: Fila thread-safe onde colocar paths de .ufdr criados
        """
        self.pending_queue = pending_queue
        super().__init__()

    def on_created(self, event: FileSystemEvent):
        """Chamado quando um arquivo é criado. Apenas enfileira para processamento após estabilização."""
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix.lower() == '.ufdr':
                logger.info(f"Arquivo UFDR criado (enfileirado): {file_path}")
                try:
                    self.pending_queue.put(file_path)
                except Exception as e:
                    logger.error(f"Erro ao enfileirar arquivo criado {file_path}: {e}")


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
        if not self.watch_directory.is_absolute():
            from argos.config import PROJECT_ROOT
            self.watch_directory = PROJECT_ROOT / self.watch_directory
        self.db_manager = db_manager or DatabaseManager()
        self.detector = UFDRDetector(self.db_manager)
        self.observer: Optional[Observer] = None
        self.callback = None
        self._pending_queue: Optional[queue.Queue] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_worker = False
        logger.info(f"UFDRMonitor inicializado. Diretório: {self.watch_directory}")

    def _worker_loop(self):
        """Thread que processa a fila: aguarda estabilização e chama o callback (nunca propaga exceção)."""
        while not self._stop_worker:
            try:
                path = self._pending_queue.get(timeout=1.0)
                if path is None:
                    break
                try:
                    wait_until_stable(path, stable_seconds=FILE_STABLE_SECONDS)
                    if self.callback:
                        self.callback(path)
                except Exception as e:
                    logger.error(
                        "Erro ao processar UFDR da fila %s: %s",
                        path, e, exc_info=True
                    )
                finally:
                    self._pending_queue.task_done()
            except queue.Empty:
                continue

    def start_monitoring(self, callback, continuous: bool = True):
        """
        Inicia monitoramento do diretório.

        Args:
            callback: Função chamada quando novo UFDR é detectado (recebe Path)
            continuous: Se True, monitora continuamente com fila e estabilização; se False, varredura única
        """
        self.callback = callback

        if continuous:
            self._pending_queue = queue.Queue()
            self._stop_worker = False
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=False)
            self._worker_thread.start()
            logger.info("Fila de processamento e worker thread iniciados")
            # Scan inicial: enfileira todos os .ufdr (sem abrir arquivo)
            logger.info("Fazendo scan inicial (enfileirando .ufdr existentes)...")
            self._scan_once_enqueue()
            event_handler = UFDRFileHandler(self._pending_queue)
            self.observer = Observer()
            self.observer.schedule(event_handler, str(self.watch_directory), recursive=False)
            self.observer.start()
            logger.info(f"Monitoramento contínuo iniciado em: {self.watch_directory}")
        else:
            self._scan_once(callback)

    def _scan_once_enqueue(self):
        """Enfileira todos os arquivos .ufdr do diretório (sem abrir). Usado no modo contínuo."""
        if not self.watch_directory.exists():
            logger.warning(f"Diretório não existe: {self.watch_directory}")
            return
        count = 0
        for p in self.watch_directory.glob("*.ufdr"):
            if p.is_file():
                self._pending_queue.put(p)
                count += 1
        if count:
            logger.info(f"Enfileirados {count} arquivo(s) .ufdr do scan inicial")
        else:
            logger.info("Nenhum arquivo .ufdr no diretório")

    def _scan_once(self, callback):
        """Faz varredura única do diretório (modo once: detect_new_files + callback)."""
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
        """Para o monitoramento e a thread worker."""
        self._stop_worker = True
        if self._pending_queue is not None:
            self._pending_queue.put(None)
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
            self._worker_thread = None
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Monitoramento parado")
        self.observer = None

    def scan(self) -> list:
        """
        Faz varredura única e retorna lista de novos arquivos.
        
        Returns:
            Lista de Paths para novos arquivos UFDR
        """
        return self.detector.detect_new_files(self.watch_directory)


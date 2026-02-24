"""
Utilitário para aguardar estabilização de arquivo (tamanho e mtime constantes).
"""

import logging
import time
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def wait_until_stable(
    path: Union[str, Path],
    stable_seconds: float = 60.0,
    check_interval: float = 2.0,
) -> None:
    """
    Aguarda o arquivo ficar estável (mesmo tamanho e mtime por stable_seconds).

    Verifica a cada check_interval segundos. Quando size e mtime permanecem
    iguais por stable_seconds consecutivos, retorna.

    Args:
        path: Caminho do arquivo
        stable_seconds: Segundos com size/mtime iguais para considerar estável (padrão: 60)
        check_interval: Intervalo entre verificações em segundos (padrão: 2)

    Raises:
        FileNotFoundError: Se o arquivo não existir ao final da espera
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    last_size = None
    last_mtime = None
    stable_since = None

    while True:
        try:
            stat = path.stat()
            size = stat.st_size
            mtime = stat.st_mtime
        except FileNotFoundError:
            raise FileNotFoundError(f"Arquivo removido durante a espera: {path}")
        except OSError as e:
            logger.warning(f"Erro ao ler stat de {path}: {e}, aguardando...")
            time.sleep(check_interval)
            continue

        if last_size is None and last_mtime is None:
            last_size, last_mtime = size, mtime
            stable_since = time.monotonic()
        elif size == last_size and mtime == last_mtime:
            elapsed = time.monotonic() - stable_since
            if elapsed >= stable_seconds:
                logger.info(f"Arquivo estável: {path} (size={size}, {stable_seconds}s)")
                return
        else:
            last_size, last_mtime = size, mtime
            stable_since = time.monotonic()

        time.sleep(check_interval)

"""
Configurações centralizadas do sistema Argos Index
"""

import os
from pathlib import Path
from typing import Optional

# Diretório raiz do projeto
PROJECT_ROOT = Path(__file__).parent.parent

# Carrega variáveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv
    # Carrega .env do diretório raiz do projeto
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        try:
            load_dotenv(dotenv_path=env_path, override=False)
        except Exception as e:
            # Se houver erro de parsing, loga mas continua
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Erro ao carregar .env (continuando sem ele): {e}")
    else:
        # Tenta carregar do diretório atual também
        load_dotenv()
except ImportError:
    # Se python-dotenv não estiver instalado, continua sem erro
    pass
except Exception as e:
    # Outros erros são ignorados silenciosamente
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Erro ao carregar .env: {e}")

# Diretórios (podem ser configurados via .env)
# Garante que sejam absolutos a partir do PROJECT_ROOT
data_dir_str = os.getenv("ARGOS_DATA_DIR", str(PROJECT_ROOT / "data"))
logs_dir_str = os.getenv("ARGOS_LOGS_DIR", str(PROJECT_ROOT / "logs"))
temp_dir_str = os.getenv("ARGOS_TEMP_DIR", str(PROJECT_ROOT / "temp"))

# Converte para Path e resolve se for relativo
# Garante que PROJECT_ROOT seja absoluto primeiro
project_root_abs = Path(PROJECT_ROOT).resolve()
DATA_DIR = Path(data_dir_str).resolve() if Path(data_dir_str).is_absolute() else (project_root_abs / data_dir_str).resolve()
LOGS_DIR = Path(logs_dir_str).resolve() if Path(logs_dir_str).is_absolute() else (project_root_abs / logs_dir_str).resolve()
TEMP_DIR = Path(temp_dir_str).resolve() if Path(temp_dir_str).is_absolute() else (project_root_abs / temp_dir_str).resolve()

# Arquivos de configuração
# Garante que sejam absolutos a partir do DATA_DIR
regex_file_str = os.getenv("ARGOS_REGEX_PATTERNS_FILE", str(DATA_DIR / "regex_patterns.json"))
db_file_str = os.getenv("ARGOS_SQLITE_DB_PATH", str(DATA_DIR / "database.db"))

regex_path = Path(regex_file_str)
db_path = Path(db_file_str)

# Se for absoluto, usa direto; senão, resolve a partir do DATA_DIR ou PROJECT_ROOT
if regex_path.is_absolute():
    REGEX_PATTERNS_FILE = regex_path.resolve()
else:
    # Tenta primeiro no DATA_DIR, depois no PROJECT_ROOT
    if (DATA_DIR / regex_path).exists() or (DATA_DIR / regex_path.name).exists():
        REGEX_PATTERNS_FILE = (DATA_DIR / regex_path.name).resolve() if (DATA_DIR / regex_path.name).exists() else (DATA_DIR / regex_path).resolve()
    else:
        REGEX_PATTERNS_FILE = (project_root_abs / regex_path).resolve()

if db_path.is_absolute():
    DATABASE_FILE = db_path.resolve()
else:
    # Tenta primeiro no DATA_DIR, depois no PROJECT_ROOT
    if (DATA_DIR / db_path).exists() or (DATA_DIR / db_path.name).exists():
        DATABASE_FILE = (DATA_DIR / db_path.name).resolve() if (DATA_DIR / db_path.name).exists() else (DATA_DIR / db_path).resolve()
    else:
        DATABASE_FILE = (project_root_abs / db_path).resolve()

# Configurações de banco de dados
DB_TYPE = os.getenv("ARGOS_DB_TYPE", "sqlite").lower()  # sqlite ou mysql

# SQLite (padrão)
SQLITE_DB_PATH = DATABASE_FILE

# MySQL (produção)
MYSQL_HOST = os.getenv("ARGOS_MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("ARGOS_MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("ARGOS_MYSQL_USER", "argos")
MYSQL_PASSWORD = os.getenv("ARGOS_MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("ARGOS_MYSQL_DATABASE", "argos_index")

# Diretório de monitoramento (pode ser local ou URL)
# Converte para Path se for caminho absoluto, senão relativo ao projeto
watch_dir_str = os.getenv("ARGOS_WATCH_DIR", str(PROJECT_ROOT / "ufdrs"))
if os.path.isabs(watch_dir_str):
    WATCH_DIRECTORY = Path(watch_dir_str)
else:
    WATCH_DIRECTORY = PROJECT_ROOT / watch_dir_str
WATCH_URL = os.getenv("ARGOS_WATCH_URL", None)  # Opcional: URL remota

# Configurações de processamento
BATCH_SIZE = int(os.getenv("ARGOS_BATCH_SIZE", "1000"))
MAX_CONTEXT_LENGTH = int(os.getenv("ARGOS_MAX_CONTEXT", "500"))

# Configurações de logging
LOG_LEVEL = os.getenv("ARGOS_LOG_LEVEL", "INFO")
LOG_FILE = Path(os.getenv("ARGOS_LOG_FILE", str(LOGS_DIR / "argos.log")))

# Criar diretórios necessários
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)


def get_database_url() -> str:
    """
    Retorna a URL de conexão do banco de dados baseado na configuração.
    
    Returns:
        str: URL de conexão (SQLite ou MySQL)
    """
    if DB_TYPE == "mysql":
        return (
            f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
            f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
        )
    else:
        # Garante que o caminho seja absoluto
        db_path = Path(SQLITE_DB_PATH).resolve()
        db_path_str = str(db_path).replace('\\', '/')
        # SQLite requer 4 barras para caminhos absolutos no Windows
        if len(db_path_str) > 1 and db_path_str[1] == ':':
            return f"sqlite:///{db_path_str}"
        else:
            return f"sqlite:///{db_path_str}"


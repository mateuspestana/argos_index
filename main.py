"""
Entry point do worker de processamento - Pipeline completo
"""

import logging
import sys
from pathlib import Path

from argos.config import LOG_FILE, LOG_LEVEL, WATCH_DIRECTORY
from argos.index.database import DatabaseManager
from argos.index.extractor import UFDRExtractor
from argos.index.text_extractor import TextExtractor
from argos.index.regex_engine import RegexEngine
from argos.watcher.monitor import UFDRMonitor
from argos.config import BATCH_SIZE

# Configuração de logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def process_ufdr(ufdr_path: Path):
    """
    Processa um arquivo UFDR completo.
    
    Pipeline:
    1. Calcula hash e extrai UFDR
    2. Extrai texto (database.db ou arquivos)
    3. Executa regex sobre textos
    4. Valida documentos sensíveis
    5. Persiste no banco de dados
    6. Limpa arquivos temporários
    
    Args:
        ufdr_path: Caminho para o arquivo .ufdr
    """
    logger.info(f"Iniciando processamento: {ufdr_path.name}")
    
    db_manager = DatabaseManager()
    extractor = UFDRExtractor()
    regex_engine = RegexEngine()
    
    try:
        # 1. Calcula ID e extrai
        ufdr_id = extractor.get_ufdr_id(ufdr_path)
        logger.info(f"UFDR ID: {ufdr_id}")
        
        # Verifica se já foi processado
        if db_manager.is_ufdr_processed(ufdr_id):
            logger.info(f"UFDR já processado: {ufdr_id}")
            return
        
        # Extrai arquivo
        extract_dir = extractor.extract(ufdr_path, ufdr_id)
        
        try:
            # 2. Extrai texto
            text_extractor = TextExtractor(extract_dir)
            text_entries = []
            regex_hits = []
            
            logger.info("Extraindo texto...")
            for text, source_path in text_extractor.extract_all():
                if text and text.strip():
                    text_entries.append((ufdr_id, text, source_path))
            
            logger.info(f"Extraídas {len(text_entries)} entradas de texto")
            
            # 3. Executa regex
            logger.info("Executando regex...")
            for ufdr_id_entry, text, source_path in text_entries:
                hits = regex_engine.process_text(text, ufdr_id)
                for type_name, value, validated, context in hits:
                    regex_hits.append((ufdr_id, type_name, value, validated, context))
            
            logger.info(f"Encontrados {len(regex_hits)} hits de regex")
            
            # 4. Persiste no banco
            logger.info("Persistindo no banco de dados...")
            
            # Adiciona UFDR file
            db_manager.add_ufdr_file(
                ufdr_id=ufdr_id,
                filename=ufdr_path.name,
                source=str(ufdr_path.parent),
                status="processed"
            )
            
            # Insere text entries em batch
            if text_entries:
                batch_size = BATCH_SIZE
                total_inserted = 0
                for i in range(0, len(text_entries), batch_size):
                    batch = text_entries[i:i + batch_size]
                    try:
                        inserted = db_manager.batch_insert_text_entries(batch)
                        total_inserted += len(batch)  # Usa tamanho do batch, não o retorno
                        logger.info(f"Inseridos {len(batch)} text entries (batch {i//batch_size + 1}, total: {total_inserted}/{len(text_entries)})")
                    except Exception as e:
                        logger.error(f"Erro ao inserir batch de text entries: {e}", exc_info=True)
                        raise
                logger.info(f"Total de {total_inserted} text entries inseridos no banco")
            else:
                logger.warning("Nenhuma entrada de texto para inserir")
            
            # Insere regex hits em batch
            if regex_hits:
                batch_size = BATCH_SIZE
                total_inserted = 0
                for i in range(0, len(regex_hits), batch_size):
                    batch = regex_hits[i:i + batch_size]
                    try:
                        inserted = db_manager.batch_insert_regex_hits(batch)
                        total_inserted += len(batch)  # Usa tamanho do batch, não o retorno
                        logger.info(f"Inseridos {len(batch)} regex hits (batch {i//batch_size + 1}, total: {total_inserted}/{len(regex_hits)})")
                    except Exception as e:
                        logger.error(f"Erro ao inserir batch de regex hits: {e}", exc_info=True)
                        raise
                logger.info(f"Total de {total_inserted} regex hits inseridos no banco")
            else:
                logger.info("Nenhum regex hit encontrado")
            
            logger.info(f"Processamento concluído com sucesso: {ufdr_path.name}")
        
        finally:
            # 5. Limpa arquivos temporários
            extractor.cleanup(extract_dir)
    
    except Exception as e:
        logger.error(f"Erro ao processar UFDR {ufdr_path}: {e}", exc_info=True)
        
        # Marca como erro no banco
        try:
            ufdr_id = extractor.get_ufdr_id(ufdr_path)
            db_manager.add_ufdr_file(
                ufdr_id=ufdr_id,
                filename=ufdr_path.name,
                source=str(ufdr_path.parent),
                status="error"
            )
        except:
            pass
        
        raise


def main():
    """Função principal"""
    logger.info("=== Argos Index Worker Iniciado ===")
    
    # Inicializa banco de dados
    db_manager = DatabaseManager()
    db_manager.create_tables()
    logger.info("Banco de dados inicializado")
    
    # Cria monitor
    monitor = UFDRMonitor()
    logger.info(f"Monitorando diretório: {monitor.watch_directory}")
    logger.info(f"Diretório existe: {monitor.watch_directory.exists()}")
    
    # Modo de operação
    import argparse
    parser = argparse.ArgumentParser(description="Argos Index Worker")
    parser.add_argument(
        "--mode",
        choices=["once", "continuous"],
        default="once",
        help="Modo de operação: once (varredura única) ou continuous (monitoramento contínuo)"
    )
    args = parser.parse_args()
    
    if args.mode == "continuous":
        logger.info("Modo contínuo ativado")
        
        def on_new_ufdr(ufdr_path: Path):
            """Callback para novos UFDRs"""
            try:
                process_ufdr(ufdr_path)
            except Exception as e:
                logger.error(f"Erro no callback: {e}", exc_info=True)
        
        monitor.start_monitoring(on_new_ufdr, continuous=True)
        
        try:
            # Mantém processo rodando
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrompido pelo usuário")
            monitor.stop_monitoring()
    
    else:
        logger.info("Modo varredura única")
        new_files = monitor.scan()
        
        if not new_files:
            logger.info("Nenhum arquivo novo encontrado")
            return
        
        logger.info(f"Encontrados {len(new_files)} arquivo(s) novo(s)")
        
        for ufdr_file in new_files:
            try:
                process_ufdr(ufdr_file)
            except Exception as e:
                logger.error(f"Erro ao processar {ufdr_file}: {e}", exc_info=True)
                continue
    
    logger.info("=== Argos Index Worker Finalizado ===")


if __name__ == "__main__":
    main()


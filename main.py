"""
Entry point do worker de processamento - Pipeline completo
"""

import logging
import sys
from pathlib import Path

from argos.config import LOG_FILE, LOG_LEVEL, WATCH_DIRECTORY, FILE_STABLE_SECONDS
from argos.utils.file_stability import wait_until_stable
from argos.index.database import DatabaseManager
from argos.index.extractor import UFDRExtractor
from argos.index.text_extractor import TextExtractor
from argos.index.metadata_extractor import UFDRMetadataExtractor
from argos.index.regex_engine import RegexEngine
from argos.index.location_history_extractor import extract_location_history_from_dir
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
    2. Extrai metadados (tipo de extração + versão Cellebrite)
    3. Extrai texto com MD5 por arquivo interno
    4. Executa regex sobre textos
    5. Persiste no banco de dados
    6. Limpa arquivos temporários
    
    Args:
        ufdr_path: Caminho para o arquivo .ufdr
    """
    logger.info(f"Iniciando processamento: {ufdr_path.name}")
    
    db_manager = DatabaseManager()
    db_manager.create_tables()  # garante schema atualizado (migrações para bases antigas)
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
            ufdr_full_path = str(ufdr_path.resolve())

            # 2. Extrai metadados (tipo de extração + versão Cellebrite)
            metadata_extractor = UFDRMetadataExtractor(extract_dir)
            ufdr_metadata = metadata_extractor.extract_metadata()
            logger.info(f"Tipo de extração: {ufdr_metadata.extraction_type}")
            logger.info(f"Versão Cellebrite: {ufdr_metadata.cellebrite_version or 'N/A'}")

            # 3. Extrai texto
            text_extractor = TextExtractor(extract_dir)
            text_entries = []
            regex_hits = []
            
            logger.info("Extraindo texto...")
            for text, source_path, file_md5 in text_extractor.extract_all():
                if text and text.strip():
                    source_name = Path(source_path).name if source_path else None
                    full_source_path = str(Path(ufdr_full_path) / source_path) if source_path else ufdr_full_path
                    text_entries.append((ufdr_id, text, source_path, source_name, full_source_path, file_md5))

            logger.info(f"Extraídas {len(text_entries)} entradas de texto")

            # 4. Executa regex
            logger.info("Executando regex...")
            for ufdr_id_entry, text, source_path, source_name, full_source_path, file_md5 in text_entries:
                hits = regex_engine.process_text(text, ufdr_id)
                for type_name, value, validated, context in hits:
                    regex_hits.append((ufdr_id, type_name, value, validated, context, source_path, file_md5))

            logger.info(f"Encontrados {len(regex_hits)} hits de regex")

            # 5. Persiste no banco
            logger.info("Persistindo no banco de dados...")

            db_manager.add_ufdr_file(
                ufdr_id=ufdr_id,
                filename=ufdr_path.name,
                source=str(ufdr_path.parent),
                full_path=ufdr_full_path,
                extraction_type=ufdr_metadata.extraction_type,
                cellebrite_version=ufdr_metadata.cellebrite_version,
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

            # 5b. Histórico de localização (*LocationHistory*.json — latitudeE7/longitudeE7)
            location_points = extract_location_history_from_dir(extract_dir)
            if location_points:
                batch_size_loc = 50_000
                for i in range(0, len(location_points), batch_size_loc):
                    batch = location_points[i : i + batch_size_loc]
                    inserted = db_manager.batch_insert_location_points(ufdr_id, batch)
                    logger.info(f"Inseridos {inserted} pontos de localização (batch {i // batch_size_loc + 1})")
            else:
                logger.debug("Nenhum arquivo Location History encontrado neste UFDR")
            
            logger.info(f"Processamento concluído com sucesso: {ufdr_path.name}")
        
        finally:
            # 5. Limpa arquivos temporários
            extractor.cleanup(extract_dir)
    
    except Exception as e:
        logger.error(f"Erro ao processar UFDR {ufdr_path}: {e}", exc_info=True)
        
        # Marca como erro no banco
        try:
            ufdr_id = extractor.get_ufdr_id(ufdr_path)
            _et = ufdr_metadata.extraction_type if 'ufdr_metadata' in locals() else None
            _cv = ufdr_metadata.cellebrite_version if 'ufdr_metadata' in locals() else None
            db_manager.add_ufdr_file(
                ufdr_id=ufdr_id,
                filename=ufdr_path.name,
                source=str(ufdr_path.parent),
                full_path=str(ufdr_path.resolve()),
                extraction_type=_et,
                cellebrite_version=_cv,
                status="error"
            )
        except Exception:
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
            """Callback para novos UFDRs. Nunca propaga exceção para o worker não interromper."""
            try:
                process_ufdr(ufdr_path)
            except Exception as e:
                logger.error(f"Erro no callback ao processar {ufdr_path}: {e}", exc_info=True)
                # Não relançar: worker continua processando outros arquivos
        
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
                wait_until_stable(ufdr_file, stable_seconds=FILE_STABLE_SECONDS)
                process_ufdr(ufdr_file)
            except Exception as e:
                logger.error(f"Erro ao processar {ufdr_file}: {e}", exc_info=True)
                continue
    
    logger.info("=== Argos Index Worker Finalizado ===")


if __name__ == "__main__":
    main()


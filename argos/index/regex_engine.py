"""
Motor de regex - Executa padrões sobre textos e integra validadores
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from argos.config import REGEX_PATTERNS_FILE, MAX_CONTEXT_LENGTH, PROJECT_ROOT
from argos.index.validators import validate_document
from argos.utils.text_utils import extract_context

logger = logging.getLogger(__name__)


class RegexEngine:
    """Motor de execução de padrões regex"""
    
    def __init__(self, patterns_file: Optional[Path] = None):
        """
        Inicializa o motor de regex.
        
        Args:
            patterns_file: Caminho para arquivo de padrões (padrão: config.REGEX_PATTERNS_FILE)
        """
        # Garante que o caminho seja absoluto a partir do PROJECT_ROOT
        # Primeiro, garante que PROJECT_ROOT seja absoluto
        project_root_abs = Path(PROJECT_ROOT).resolve()
        
        if patterns_file:
            patterns_path = Path(patterns_file)
            if patterns_path.is_absolute():
                self.patterns_file = patterns_path
            else:
                # Se for relativo, resolve a partir do PROJECT_ROOT absoluto
                self.patterns_file = project_root_abs / patterns_path
        else:
            # REGEX_PATTERNS_FILE pode ser Path ou string
            patterns_path = Path(REGEX_PATTERNS_FILE) if not isinstance(REGEX_PATTERNS_FILE, Path) else REGEX_PATTERNS_FILE
            if patterns_path.is_absolute():
                self.patterns_file = patterns_path
            else:
                # Se for relativo, resolve a partir do PROJECT_ROOT absoluto
                self.patterns_file = project_root_abs / patterns_path
        
        # Resolve para caminho absoluto final (garante que seja absoluto mesmo se PROJECT_ROOT for relativo)
        self.patterns_file = self.patterns_file.resolve()
        
        self.patterns: List[Dict] = []
        self.compiled_patterns: List[Tuple[re.Pattern, Dict]] = []
        self._load_patterns()
    
    def _load_patterns(self):
        """Carrega padrões do arquivo JSON"""
        try:
            # self.patterns_file já é absoluto e resolvido
            if not self.patterns_file.exists():
                logger.error(f"Arquivo de padrões não encontrado: {self.patterns_file}")
                logger.error(f"Diretório atual: {Path.cwd()}")
                logger.error(f"PROJECT_ROOT: {PROJECT_ROOT}")
                logger.error(f"REGEX_PATTERNS_FILE config: {REGEX_PATTERNS_FILE}")
                raise FileNotFoundError(f"Arquivo de padrões não encontrado: {self.patterns_file}")
            
            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.patterns = data.get('patterns', [])
            
            # Compila padrões
            for pattern in self.patterns:
                try:
                    regex_str = pattern['regex']
                    name = pattern['name']
                    ignore_case = pattern.get('ignoreCase', False)
                    
                    # Compila regex com flags apropriadas
                    flags = re.IGNORECASE if ignore_case else 0
                    compiled = re.compile(regex_str, flags)
                    
                    self.compiled_patterns.append((compiled, pattern))
                    logger.debug(f"Padrão compilado: {name}")
                
                except re.error as e:
                    logger.warning(f"Erro ao compilar padrão {pattern.get('name', 'unknown')}: {e}")
                except Exception as e:
                    logger.warning(f"Erro ao processar padrão: {e}")
            
            logger.info(f"Carregados {len(self.compiled_patterns)} padrões regex de {self.patterns_file}")
        
        except FileNotFoundError as e:
            logger.error(f"Arquivo de padrões não encontrado: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro ao carregar padrões: {e}")
            raise
    
    def process_text(
        self,
        text: str,
        ufdr_id: str
    ) -> List[Tuple[str, str, bool, Optional[str]]]:
        """
        Processa um texto executando todos os padrões regex.
        
        Args:
            text: Texto para processar
            ufdr_id: ID do UFDR (para contexto)
        
        Returns:
            Lista de tuplas (type, value, validated, context)
        """
        hits = []
        
        if not text:
            return hits
        
        # Executa cada padrão
        for compiled_pattern, pattern_info in self.compiled_patterns:
            pattern_name = pattern_info['name']
            
            try:
                # Encontra todas as ocorrências
                matches = compiled_pattern.finditer(text)
                
                for match in matches:
                    value = match.group(0)
                    start_pos = match.start()
                    
                    # Extrai contexto
                    context = extract_context(text, start_pos, MAX_CONTEXT_LENGTH)
                    
                    # Valida se necessário
                    validated = False
                    if pattern_name.startswith('BR_'):
                        # Documentos brasileiros precisam validação
                        validated = validate_document(pattern_name, value)
                    
                    hits.append((pattern_name, value, validated, context))
            
            except Exception as e:
                logger.warning(f"Erro ao processar padrão {pattern_name}: {e}")
                continue
        
        return hits
    
    def get_pattern_names(self) -> List[str]:
        """
        Retorna lista de nomes de padrões carregados.
        
        Returns:
            Lista de nomes de padrões
        """
        return [pattern['name'] for pattern in self.patterns]
    
    def get_pattern_by_name(self, name: str) -> Optional[Dict]:
        """
        Retorna informações de um padrão específico.
        
        Args:
            name: Nome do padrão
        
        Returns:
            Dict com informações do padrão ou None
        """
        for pattern in self.patterns:
            if pattern['name'] == name:
                return pattern
        return None


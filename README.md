# Argos Index - Sistema de Extração, Indexação e Busca em Arquivos UFDR

Sistema completo para automatizar a ingestão, extração, indexação e consulta de informações contidas em arquivos `.ufdr`, com foco em investigação, análise forense digital e busca textual estruturada.

## 📋 Características

- **Monitoramento Automático**: Detecta novos arquivos UFDR automaticamente
- **Extração Inteligente**: Extrai texto de database.db (SQLite/PostgreSQL) ou arquivos texto
- **Motor de Regex**: Executa padrões regex sobre todo o corpus extraído
- **Validação de Documentos**: Valida CPF, CNPJ e CNH usando algoritmos de dígito verificador
- **Interface Web**: Interface Streamlit para busca textual e por entidades
- **Persistência Flexível**: Suporta SQLite (desenvolvimento) e MySQL (produção)

## 🏗️ Arquitetura

O sistema é composto por três módulos principais:

1. **Watcher**: Monitora diretórios e detecta novos arquivos UFDR
2. **Index**: Processa, extrai e indexa conteúdo dos UFDRs
3. **Argos Client**: Interface Streamlit para consulta e exploração

## 📦 Instalação

### Pré-requisitos

- Python 3.12+
- Ambiente virtual `.venv` (já configurado no projeto)

### Instalar Dependências

```bash
# Usando uv (recomendado)
uv pip install -r requirements.txt

# Ou usando pip do venv
.venv/bin/pip install -r requirements.txt
```

### Configurar Ambiente

1. **Copie o arquivo de configuração:**
   ```bash
   # Linux/Mac
   cp .env.example .env
   
   # Windows
   copy .env.example .env
   ```

2. **Edite o arquivo `.env`** conforme necessário (veja seção [Configuração](#-configuração) abaixo).

## 🚀 Uso

### 1. Processar Arquivos UFDR

#### Modo Varredura Única

Processa todos os arquivos UFDR novos encontrados no diretório configurado:

```bash
.venv/bin/python main.py --mode once
```

#### Modo Contínuo

Monitora o diretório continuamente e processa novos arquivos automaticamente:

```bash
.venv/bin/python main.py --mode continuous
```

### 2. Interface Web (Streamlit)

Inicia a interface web para busca e exploração:

```bash
# Usando o script (recomendado)
./run_client.sh

# Ou diretamente
cd argos/client
PYTHONPATH=../.. ../../.venv/bin/streamlit run app.py
```

A interface estará disponível em `http://localhost:8501` com navegação moderna usando `st.Page` e `st.navigation`.

A interface estará disponível em `http://localhost:8501`

## ⚙️ Configuração

### Configuração via Arquivo .env (Recomendado)

O sistema utiliza um arquivo `.env` para configurações. Para começar:

1. **Copie o arquivo de exemplo:**
   ```bash
   # Linux/Mac
   cp .env.example .env
   
   # Windows
   copy .env.example .env
   ```

2. **Edite o arquivo `.env`** com suas configurações:
   ```bash
   # Exemplo: Monitorar diretório em outro drive (Windows)
   ARGOS_WATCH_DIR=D:\UFDRs
   
   # Exemplo: Usar MySQL em produção
   ARGOS_DB_TYPE=mysql
   ARGOS_MYSQL_HOST=localhost
   ARGOS_MYSQL_USER=argos
   ARGOS_MYSQL_PASSWORD=sua_senha
   ```

### Variáveis de Configuração Disponíveis

Todas as configurações podem ser definidas no arquivo `.env`:

#### Banco de Dados
- `ARGOS_DB_TYPE`: Tipo de banco (`sqlite` ou `mysql`)
- `ARGOS_SQLITE_DB_PATH`: Caminho do banco SQLite (padrão: `data/database.db`)
- `ARGOS_MYSQL_HOST`: Host MySQL (padrão: `localhost`)
- `ARGOS_MYSQL_PORT`: Porta MySQL (padrão: `3306`)
- `ARGOS_MYSQL_USER`: Usuário MySQL (padrão: `argos`)
- `ARGOS_MYSQL_PASSWORD`: Senha MySQL
- `ARGOS_MYSQL_DATABASE`: Nome do banco MySQL (padrão: `argos_index`)

#### Monitoramento
- `ARGOS_WATCH_DIR`: Diretório para monitorar (padrão: `ufdrs`)
- `ARGOS_WATCH_URL`: URL remota (opcional)

#### Processamento
- `ARGOS_BATCH_SIZE`: Tamanho do batch para inserções (padrão: `1000`)
- `ARGOS_MAX_CONTEXT`: Tamanho máximo do contexto (padrão: `500`)

#### Logging
- `ARGOS_LOG_LEVEL`: Nível de log (padrão: `INFO`)
- `ARGOS_LOG_FILE`: Caminho do arquivo de log (padrão: `logs/argos.log`)

#### Diretórios
- `ARGOS_DATA_DIR`: Diretório de dados (padrão: `data`)
- `ARGOS_LOGS_DIR`: Diretório de logs (padrão: `logs`)
- `ARGOS_TEMP_DIR`: Diretório temporário (padrão: `temp`)
- `ARGOS_REGEX_PATTERNS_FILE`: Arquivo de padrões regex (padrão: `data/regex_patterns.json`)

### Configuração via Variáveis de Ambiente (Alternativa)

Se preferir, você ainda pode usar variáveis de ambiente diretamente:

```bash
# Linux/Mac
export ARGOS_WATCH_DIR=/home/user/UFDRs
export ARGOS_DB_TYPE=mysql

# Windows (PowerShell)
$env:ARGOS_WATCH_DIR = "D:\UFDRs"
$env:ARGOS_DB_TYPE = "mysql"
```

**Nota:** O arquivo `.env` tem prioridade sobre variáveis de ambiente do sistema.

## 📁 Estrutura do Projeto

```
ufdr_reader/
├── argos/                    # Módulo principal
│   ├── config.py            # Configurações (lê .env)
│   ├── watcher/             # Monitoramento
│   ├── index/               # Indexação e processamento
│   ├── client/              # Interface Streamlit
│   └── utils/               # Utilitários
├── data/                     # Dados e configurações
│   ├── regex_patterns.json  # Padrões regex
│   └── database.db          # Banco SQLite (criado automaticamente)
├── logs/                     # Logs do sistema
├── temp/                     # Arquivos temporários de extração
├── ufdrs/                    # Diretório de arquivos UFDR
├── .env.example              # Exemplo de configuração (copie para .env)
├── .env                      # Configurações do sistema (criar a partir de .env.example)
├── main.py                   # Entry point do worker
└── requirements.txt          # Dependências
```

## 🔍 Funcionalidades da Interface

### Busca Textual

- Busca livre em todo o corpus indexado
- Filtros por UFDR específico
- Exibição de contexto e origem

### Busca por Entidades

- Filtro por tipo de entidade (CPF, email, crypto, etc.)
- Filtro por valor específico
- Filtro por validação (válidos/inválidos)
- Exportação para CSV

### Estatísticas

- Total de UFDRs processados
- Total de entradas de texto
- Total de hits de regex
- Distribuição por tipo de entidade
- Estatísticas de validação

### UFDRs Processados

- Lista completa de arquivos processados
- Informações de status e data de processamento

## 🛠️ Desenvolvimento

### Estrutura de Módulos

- **argos/watcher/**: Detecção e monitoramento de arquivos
- **argos/index/**: Extração, regex e persistência
- **argos/client/**: Interface Streamlit
- **argos/utils/**: Utilitários (hashing, normalização de texto)

### Padrões Regex

Os padrões regex são carregados de `data/regex_patterns.json`. O arquivo suporta:

- Padrões com flags `ignoreCase`
- Prefixo e sufixo para contexto
- Validação automática para documentos brasileiros

### Validação de Documentos

Documentos brasileiros (CPF, CNPJ, CNH) são validados automaticamente usando algoritmos de dígito verificador. Valores inválidos são mantidos no banco mas marcados como `validated = false`.

## 📝 Logs

Os logs são salvos em `logs/argos.log` e também exibidos no console. O nível de log pode ser configurado via `ARGOS_LOG_LEVEL`.

## 🔒 Segurança

- IDs determinísticos usando SHA-256
- Processamento isolado em diretórios temporários
- Limpeza automática após processamento
- Suporte a ambiente isolado

## 📄 Licença

Este projeto foi desenvolvido por Matheus C. Pestana.

## 🤝 Contribuindo

Para contribuir, siga as boas práticas:

- Código modular e testável
- Logs estruturados
- Tratamento robusto de exceções
- Documentação clara

## 🔧 Troubleshooting

### Problemas com .env

Se você encontrar erros ao carregar o arquivo `.env`:

1. **Execute o script de diagnóstico:**
   ```bash
   python check_config.py
   ```

2. **Verifique o formato do .env:**
   - Cada linha deve ser: `VARIAVEL=valor`
   - Linhas começando com `#` são comentários
   - Não use espaços ao redor do `=`
   - Use aspas apenas se o valor contiver espaços

3. **Erro "python-dotenv could not parse":**
   - Verifique se o arquivo está em UTF-8
   - Remova BOM (Byte Order Mark) se existir
   - Certifique-se de que não há caracteres especiais no início

### Watcher não está indexando

Se o watcher não está processando arquivos:

1. **Verifique o diretório configurado:**
   ```bash
   python check_config.py
   ```

2. **Confirme que o diretório existe:**
   - O diretório em `ARGOS_WATCH_DIR` deve existir
   - Verifique permissões de leitura

3. **Reinicie o watcher:**
   - Pare o processo atual (Ctrl+C)
   - Execute novamente: `python main.py --mode continuous`

## 🔄 Reset do Banco de Dados

Para resetar/zerar o banco de dados:

### Opção 1: Usando o script (Recomendado)
```bash
python reset_database.py
```

O script:
- Mostra estatísticas do banco atual
- Solicita confirmação
- Deleta o banco e recria um novo vazio

### Opção 2: Deletar manualmente
```bash
# Simplesmente delete o arquivo
rm data/database.db

# O banco será recriado automaticamente na próxima execução
```

**Nota:** O banco será recriado automaticamente na próxima execução do sistema.

## 📞 Suporte

Para questões ou problemas, consulte os logs em `logs/argos.log` ou verifique a documentação em `PROJECT.md`.


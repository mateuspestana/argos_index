# Changelog

Todas as mudanças notáveis do Argos Index são documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [1.2.0] - Atual

### Adicionado

- **Hash MD5 por arquivo interno**: cada arquivo processado dentro do UFDR gera hash MD5. Para entradas extraídas de `database.db`, o MD5 é do `database.db`; para entradas extraídas de arquivos texto, o MD5 é do arquivo individual. O MD5 está presente nas tabelas `text_entries` e `regex_hits` e é exibido nas páginas de busca textual, busca por entidades e demais interfaces do client.
- **Tipo de extração (Apple/Google)**: cada UFDR processado indica se a extração é de um dispositivo Apple (iOS) ou Google (Android), com base nos metadados do UFDR (`report.xml`, tabelas `ExtractionInfos`/`DeviceInfos` do `database.db`, nomes de dispositivo). Exibido na lista de UFDRs processados e nas estatísticas.
- **Versão do Cellebrite**: cada UFDR exibe a versão do Cellebrite UFED utilizada na extração, quando disponível nos metadados internos. Exibido na lista de UFDRs processados.
- **Novo módulo `metadata_extractor.py`**: extrator dedicado de metadados de UFDR (tipo de extração + versão Cellebrite). Analisa `report.xml`, banco SQLite interno, dump PostgreSQL e estrutura de diretórios.
- **Estatísticas de tipo de extração**: página de Estatísticas exibe contagem de UFDRs por tipo de extração (Apple, Google (Android), Desconhecido).

### Alterado

- **`TextExtractor.extract_all()`**: agora retorna 3-tuplas `(texto, source_path, file_md5)` ao invés de 2-tuplas.
- **`batch_insert_text_entries()`**: aceita 6-tuplas `(ufdr_id, content, source_path, source_name, full_source_path, file_md5)`.
- **`batch_insert_regex_hits()`**: aceita 7-tuplas `(ufdr_id, type, value, validated, context, source_path, file_md5)`.
- **`add_ufdr_file()`**: aceita novos parâmetros `extraction_type` e `cellebrite_version`.
- **Pipeline de processamento**: extrai metadados e calcula MD5 por arquivo interno antes da persistência.

### Migração

- Bancos criados antes da 1.2.0 precisam das novas colunas. Em SQLite, execute:
  ```sql
  ALTER TABLE ufdr_files ADD COLUMN extraction_type VARCHAR(50);
  ALTER TABLE ufdr_files ADD COLUMN cellebrite_version VARCHAR(50);
  ALTER TABLE text_entries ADD COLUMN file_md5 CHAR(32);
  ALTER TABLE regex_hits ADD COLUMN file_md5 CHAR(32);
  ```
- Registros antigos terão `NULL` nessas colunas; a interface usa fallback ("N/A").

---

## [1.1.3]

### Adicionado

- **Extração estruturada de dumps PostgreSQL (Cellebrite)**: quando o `database.db` é um dump PostgreSQL custom, usa `pg_restore` para extrair dados de forma estruturada.
- **Relacionamento com SourceInfoNodes**: extrai a tabela `SourceInfoNodes` para relacionar dados com arquivos originais quando `SourceInfoId` está disponível.
- **Novo formato de source_path**: dados do dump PostgreSQL agora usam formato `database.db:NomeTabela` (ex: `database.db:Coordinates`, `database.db:Contacts`) ao invés do genérico `postgresql_dump`.
- **Identificação de extração**: obtém nome do dispositivo/extração via tabela `ExtractionInfos` para contexto.
- **Fallback robusto**: quando `pg_restore` não está disponível, usa extração básica mantendo compatibilidade.

---

## [1.1.2]

### Adicionado

- **Múltiplos workers**: no modo contínuo, várias threads passam a consumir a mesma fila de UFDRs em paralelo. Padrão de 5 workers; configurável via `ARGOS_NUM_WORKERS` no `.env`. Valores menores que 1 são tratados como 1.

---

## [1.1.1]

### Corrigido

- **Estabilização de arquivo**: se o arquivo for removido durante a espera por estabilização (`wait_until_stable`), o código passava a entrar em loop infinito ao tratar o erro como genérico. Agora `FileNotFoundError` é relançada com mensagem clara (“Arquivo removido durante a espera”).
- **Banco de dados**: import de `os` movido para o topo do módulo em `database.py`; lógica de `full_path` em `add_ufdr_file` quando `source` é `None` deixada explícita.

---

## [1.1.0]

### Adicionado

- **Estabilização de arquivo antes de processar**: o watcher não abre mais o arquivo assim que ele aparece; aguarda o arquivo ficar estável (mesmo tamanho e `mtime` por 60 segundos, configurável via `ARGOS_FILE_STABLE_SECONDS`) antes de tentar abrir. Evita erros quando o UFDR ainda está sendo transferido.
- **Retry em permission denied**: ao abrir o arquivo para hash ou extração, em caso de permission denied (EACCES/EPERM) o sistema faz até 5 tentativas com backoff (2s, 5s, 10s, 15s, 20s). Configurável com `ARGOS_PERMISSION_DENIED_RETRIES` e `RETRY_DELAYS`.
- **Fila de processamento no modo contínuo**: em vez de processar no evento `on_created`, os paths são enfileirados; uma thread worker aplica estabilização e depois chama o processamento. Enquanto um arquivo aguarda estabilização ou retry, outros da fila podem ser processados.
- **Worker resiliente**: o callback de processamento nunca propaga exceção; um UFDR com falha não interrompe o worker. No modo varredura única (`once`), cada arquivo passa por estabilização e falhas são logadas com `continue`.
- **Caminho completo do UFDR**: nova coluna `full_path` em `ufdr_files`; persistido ao registrar o UFDR. Na lista de UFDRs processados, exibida a coluna "Caminho completo do UFDR".
- **Nome e caminho completo para arquivos internos**: em `text_entries`, colunas `source_name` (nome do arquivo) e `full_source_path` (caminho completo da entrada dentro do UFDR). Em `regex_hits`, coluna `source_path` (caminho interno onde o hit foi encontrado). Todas as referências no client passam a exibir nome do arquivo e caminhos completos (interno e do UFDR).
- **Página de cruzamentos**: nova página "Cruzamentos" no menu Análise. Permite filtrar por tipo de entidade (CPF, CNPJ, e-mail, etc.) e lista valores que aparecem em **mais de um UFDR**, com quantidade de arquivos e detalhe dos UFDRs (nome e caminho completo) onde cada valor aparece.

### Alterado

- **Watcher**: no modo contínuo, `on_created` apenas enfileira o path (não calcula hash nem abre o arquivo). Scan inicial enfileira todos os `.ufdr` do diretório para processamento após estabilização.
- **Busca textual**: expander de cada resultado exibe nome do arquivo, caminho completo do arquivo (interno), caminho completo do UFDR, além do caminho interno e do nome do UFDR.
- **Busca por entidades**: tabela de resultados inclui colunas "Nome do arquivo", "Caminho completo do arquivo (interno)" e "Caminho completo do UFDR".
- **API de banco**: `add_ufdr_file` aceita parâmetro opcional `full_path`. `batch_insert_text_entries` passa a receber tuplas de 5 elementos `(ufdr_id, content, source_path, source_name, full_source_path)`. `batch_insert_regex_hits` passa a receber tuplas de 6 elementos `(ufdr_id, type, value, validated, context, source_path)`.

### Migração

- Bancos criados antes da 1.1 precisam das novas colunas. Em SQLite, execute (se ainda não existirem):
  ```sql
  ALTER TABLE ufdr_files ADD COLUMN full_path TEXT;
  ALTER TABLE text_entries ADD COLUMN source_name TEXT;
  ALTER TABLE text_entries ADD COLUMN full_source_path TEXT;
  ALTER TABLE regex_hits ADD COLUMN source_path TEXT;
  ```
- Registros antigos terão `NULL` nessas colunas; a interface usa fallback (ex.: montar caminho a partir de `source` e `filename`).

---

## [1.0.0]

### Características iniciais

- Monitoramento de diretório para arquivos `.ufdr` (modo varredura única e contínuo).
- Extração de conteúdo de UFDR (ZIP) e de texto em `database.db` ou arquivos de texto.
- Motor de regex com padrões configuráveis e validação de documentos (CPF, CNPJ, CNH).
- Persistência em SQLite ou MySQL (ufdr_files, text_entries, regex_hits).
- Interface Streamlit: busca textual, busca por entidades, estatísticas, lista de UFDRs processados.

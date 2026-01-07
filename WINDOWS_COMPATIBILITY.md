# Compatibilidade com Windows

## ✅ Funcionamento em Windows

O sistema **funciona perfeitamente no Windows**, incluindo:
- ✅ Caminhos em outros drives (D:, E:, etc.)
- ✅ Caminhos absolutos
- ✅ Caminhos com espaços
- ✅ Diretórios diferentes de `ufdrs/`

## 🔧 Configuração para Windows

### Método Recomendado: Arquivo .env

A forma mais fácil de configurar é usando o arquivo `.env`:

1. **Copie o arquivo de exemplo:**
   ```cmd
   copy .env.example .env
   ```

2. **Edite o arquivo `.env`** com um editor de texto:
   ```env
   # Exemplo: Monitorar diretório em outro drive
   ARGOS_WATCH_DIR=D:\UFDRs
   
   # Exemplo: Banco de dados em outro local
   ARGOS_SQLITE_DB_PATH=D:\ArgosData\database.db
   ```

3. **Salve o arquivo** e execute o sistema normalmente.

### Método Alternativo: Variáveis de Ambiente

Se preferir usar variáveis de ambiente diretamente:

**PowerShell:**
```powershell
$env:ARGOS_WATCH_DIR = "D:\UFDRs"
```

**CMD:**
```cmd
set ARGOS_WATCH_DIR=D:\UFDRs
```

**Permanente (variável de sistema):**
1. Painel de Controle → Sistema → Configurações avançadas do sistema
2. Variáveis de ambiente → Novo (usuário ou sistema)
3. Nome: `ARGOS_WATCH_DIR`
4. Valor: `D:\UFDRs` (ou o caminho desejado)

### 2. Caminhos Absolutos

O sistema aceita caminhos absolutos normalmente:

```powershell
# Exemplo: monitorar pasta em outro drive
$env:ARGOS_WATCH_DIR = "E:\Investigacoes\UFDRs"
```

### 3. Caminhos com Espaços

Caminhos com espaços funcionam normalmente:

```powershell
$env:ARGOS_WATCH_DIR = "C:\Meus Documentos\UFDRs"
```

### 4. Banco de Dados em Local Diferente

O banco de dados SQLite também pode estar em outro local. Configure no arquivo `.env`:

```env
# No arquivo .env
ARGOS_SQLITE_DB_PATH=D:\ArgosData\database.db
```

Ou via variável de ambiente:
```powershell
$env:ARGOS_SQLITE_DB_PATH = "D:\ArgosData\database.db"
```

## 📝 Exemplos de Uso

### Exemplo 1: Monitorar pasta em drive D: (usando .env)

**Criar/editar arquivo `.env`:**
```env
ARGOS_WATCH_DIR=D:\UFDRs
ARGOS_LOG_LEVEL=INFO
```

**Executar:**
```cmd
python main.py --mode continuous
```

**Ou via PowerShell:**
```powershell
$env:ARGOS_WATCH_DIR = "D:\UFDRs"
python main.py --mode continuous
```

### Exemplo 2: Processar arquivo específico

```python
from pathlib import Path
from main import process_ufdr

# Processar UFDR de qualquer local
ufdr_path = Path("E:\\Investigacoes\\caso123.ufdr")
process_ufdr(ufdr_path)
```

### Exemplo 3: Configuração completa via .env

**Criar arquivo `.env`:**
```env
# Diretório de monitoramento
ARGOS_WATCH_DIR=D:\UFDRs

# Banco de dados
ARGOS_DB_TYPE=sqlite
ARGOS_SQLITE_DB_PATH=D:\ArgosData\database.db

# Logging
ARGOS_LOG_LEVEL=INFO
ARGOS_LOG_FILE=D:\ArgosData\logs\argos.log

# Processamento
ARGOS_BATCH_SIZE=1000
ARGOS_MAX_CONTEXT=500
```

**Executar:**
```cmd
python main.py
```

## 🔍 Verificações

O sistema usa `pathlib.Path` que é **totalmente multiplataforma**:
- ✅ Converte automaticamente barras invertidas `\` para `/` quando necessário
- ✅ Funciona com caminhos absolutos e relativos
- ✅ Suporta UNC paths (`\\server\share`)
- ✅ Suporta caminhos longos no Windows 10+

## ⚠️ Observações

1. **Permissões**: Certifique-se de que o usuário tem permissões de leitura/escrita no diretório configurado
2. **Caminhos longos**: Windows tem limite de 260 caracteres por padrão, mas o Python 3.6+ suporta caminhos longos automaticamente
3. **Case sensitivity**: Windows não diferencia maiúsculas/minúsculas em nomes de arquivos, mas o sistema preserva o case original

## 🧪 Teste Rápido

Para testar se está funcionando:

```python
from pathlib import Path
from argos.config import WATCH_DIRECTORY

# Verificar diretório configurado
print(f"Diretório monitorado: {WATCH_DIRECTORY}")
print(f"Existe: {Path(WATCH_DIRECTORY).exists()}")
```


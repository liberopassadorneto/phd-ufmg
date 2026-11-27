# YouTube Multimodal Scraper (`yt-scraper`)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![yt-dlp](https://img.shields.io/badge/yt--dlp-Extractor-FF0000?logo=youtube&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-phd__pipeline-4169E1?logo=postgresql&logoColor=white)
![S3 Storage](https://img.shields.io/badge/Storage-S3%20Compatible-569A31?logo=amazons3&logoColor=white)
![Status](https://img.shields.io/badge/Status-Funcional%20(Em%20Evolu%C3%A7%C3%A3o)-d97706)

Pipeline paralela de extração seletiva de ativos multimodais do YouTube (áudio em MP3, legendas em português, miniaturas e *frames* periódicos) orientada por CSV, com rotação de proxies SOCKS5, persistência em armazenamento S3 e registro de metadados no PostgreSQL (`phd_pipeline`).

O projeto foi desenvolvido para coleta em larga escala de dados audiovisuais em português no contexto de pesquisa acadêmica na UFMG. Embora funcional em produção (com dezenas de milhares de vídeos já extraídos), sua arquitetura atual ainda possui características de protótipo operacional: a entrada depende de exportação manual de CSV, o filtro de idioma baseia-se exclusivamente nos metadados retornados pelo cliente `android` do `yt-dlp` (sem detecção acústica de fala) e a extração de *frames* via `ffmpeg` representa o principal gargalo de CPU em execuções paralelas.

## Funcionalidades e Módulos

| Item | Descrição |
| :--- | :--- |
| `src/manager.py` | Orquestrador paralelo (`ProcessPoolExecutor`). Lê o `config.conf`, filtra IDs já sincronizados no PostgreSQL e listas de exclusão (`ids_foreign.txt`, `ids_undetermined.txt`), fatia a carga entre *workers* por arquivo de cookie, gerencia *cooldown* de 90 minutos em bloqueios e consolida relatórios de execução. |
| `src/video_downloader.py` | Extrator isolado por subprocesso. Realiza consulta única de metadados (`extract_info`), classifica o idioma (`pt`, `foreign`, `ambiguous` ou `unknown`), seleciona legendas manuais ou automáticas originais (`pt-orig`), rotaciona proxies SOCKS5 em bloqueios de IP e extrai *frames* (1 a cada 10s) com `ffmpeg`. |
| `src/storage_sync.py` | Camada de persistência. Faz upload recursivo dos arquivos brutos para o *bucket* S3 (`data/<youtube_video_id>/...`) e executa *upsert* dos metadados consolidados na tabela `phd_pipeline.extraction`. |
| `src/bot.py` | Interface de controle remoto via Telegram (`/start` e `/stop` restritos ao `chat_id` autorizado) para disparo em segundo plano (`nohup`), parada segura via arquivo-sinal `STOP_EXTRACTION` e envio de alertas de bloqueio e relatórios. |
| `config.conf` | Arquivo INI centralizando diretórios, flags de modalidades (`extrair_audio`, `extrair_subs`, `extrair_frames`, `extrair_thumb`), lista de proxies, credenciais do Telegram, S3 e PostgreSQL. |

## Como Executar

### Pré-requisitos
- Python 3.11+ e gerenciador de pacotes `uv`
- `ffmpeg` instalado e disponível no `PATH` do sistema
- Instância PostgreSQL acessível com o esquema `phd_pipeline` e a tabela `video` populada
- Serviço de armazenamento compatível com S3 (ex.: AWS S3, MinIO ou local-s3)
- Pelo menos um arquivo de cookies válido no formato Netscape (`.txt`) dentro do diretório configurado em `cookies_dir`
- Arquivo CSV de entrada contendo a coluna `video_id` (ou `Video_id`)

### Passos gerais

```bash
# 1. Clonar o repositório
git clone [https://github.com/phd-ufmg/yt-scraper.git](https://github.com/phd-ufmg/yt-scraper.git)
cd yt-scraper

# 2. Instalar dependências com uv
uv sync

# 3. Preparar o diretório de cookies e o arquivo de configuração
mkdir -p cookies output
cp /caminho/para/seus_cookies.txt cookies/perfil_1.txt

cat << 'EOF' > config.conf
[DEFAULT]
cookies_dir = cookies
output_dir = output
csv_alvo = lista_alvos.csv
extrair_audio = true
extrair_subs = true
extrair_frames = true
extrair_thumb = true
using_proxy = false
proxies_list =

[TELEGRAM]
bot_token =
chat_id =

[S3]
endpoint = http://localhost
port = 9000
access_key = sua_access_key
secret_key = sua_secret_key
bucket_name = youtube-assets

[POSTGRES]
host = localhost
port = 5432
dbname = phd_db
user = postgres
password = sua_senha
EOF

# 4. Executar a pipeline diretamente (ou via bot do Telegram com /start)
uv run src/manager.py --conf config.conf
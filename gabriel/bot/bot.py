import configparser
from datetime import datetime
import logging
import os
import subprocess
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest

# Configurar logs
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

PROJECT_DIR = "/home/marcele_araponga/phd-ufmg/gabriel/yt-scraper"

# Ler o token e configurações do config.conf do projeto (mesmo usado pelo manager)
config = configparser.ConfigParser()
config.read(os.path.join(PROJECT_DIR, "config.conf"))

TOKEN = config.get("TELEGRAM", "bot_token")
AUTHORIZED_CHAT_ID = config.get("TELEGRAM", "chat_id", fallback="").strip()

# Deve ser o mesmo arquivo monitorado pelo manager.py (STOP_FILE)
STOP_FILE = os.path.join(PROJECT_DIR, "STOP_EXTRACTION")


def is_authorized(update: Update) -> bool:
    """Aceita comandos apenas do chat configurado em [TELEGRAM] chat_id."""
    return str(update.effective_chat.id) == AUTHORIZED_CHAT_ID


def is_manager_running() -> bool:
    """Verifica se já existe uma instância de src/manager.py em execução."""
    result = subprocess.run(
        ["pgrep", "-f", "src/manager.py"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def build_ipv4_request() -> HTTPXRequest:
    """Cria um HTTPXRequest forçando IPv4 (0.0.0.0) e timeouts tolerantes."""
    req = HTTPXRequest(
        connect_timeout=15.0,
        read_timeout=15.0,
        write_timeout=15.0,
        pool_timeout=15.0,
    )
    req._client_kwargs["transport"] = httpx.AsyncHTTPTransport(
        local_address="0.0.0.0"
    )
    return req


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra erros transientes de rede sem derrubar o polling do bot."""
    logger.warning("Erro na comunicacao com o Telegram: %s", context.error)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    user = update.effective_user
    logger.info(f"Comando /start recebido de {user.username} (ID: {user.id})")

    if is_manager_running():
        await update.message.reply_text(
            "Já existe uma execução de `src/manager.py` rodando no servidor.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("Iniciando a extração localmente no servidor...")

    try:
        data_atual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"extracao_{data_atual}.log"

        command = (
            f"cd {PROJECT_DIR} && "
            f"nohup uv run src/manager.py > {log_filename} 2>&1 &"
        )

        logger.info(f"Executando localmente: {command}")
        subprocess.run(command, shell=True, check=True)

        await update.message.reply_text(
            f"**Processo iniciado com sucesso no servidor!**\n\n"
            f"**Log gerado:** `{log_filename}`",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Erro ao executar comando: {e}")
        await update.message.reply_text(
            f"**Erro ao iniciar script:**\n`{str(e)}`", parse_mode="Markdown"
        )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pede parada segura: cada worker termina o vídeo atual e encerra."""
    if not is_authorized(update):
        return
    logger.info("Comando /stop recebido")
    try:
        with open(STOP_FILE, "w") as f:
            f.write(datetime.now().isoformat())
        await update.message.reply_text(
            "Parada segura solicitada. Cada worker termina o vídeo atual "
            "(download, S3 e Postgres) e encerra; workers em espera "
            "encerram em até ~10 s."
        )
    except Exception as e:
        logger.error(f"Erro ao criar sinal de parada: {e}")
        await update.message.reply_text(f"Erro ao solicitar parada: {e}")


def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .request(build_ipv4_request())
        .get_updates_request(build_ipv4_request())
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_error_handler(on_error)

    print(">> Bot rodando localmente (IPv4) e ouvindo /start e /stop...")
    app.run_polling()


if __name__ == "__main__":
    main()

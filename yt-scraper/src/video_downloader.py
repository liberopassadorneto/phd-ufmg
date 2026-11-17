import argparse
import glob
import os
import shutil
import subprocess
import sys
import yt_dlp

current_proxy_index = 0
PROXY_INDEX_FILE = "proxy_index.txt"


def load_proxy_index(cookies_dir):
    """Lê o índice do último proxy usado (cada vídeo roda em um processo novo)."""
    try:
        with open(os.path.join(cookies_dir, PROXY_INDEX_FILE)) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def save_proxy_index(cookies_dir, index):
    """Persiste o índice do proxy atual para as próximas execuções do perfil."""
    os.makedirs(cookies_dir, exist_ok=True)
    with open(os.path.join(cookies_dir, PROXY_INDEX_FILE), "w") as f:
        f.write(str(index))


class _SilentLogger:
    """Suprime mensagens de debug, avisos e progresso do yt-dlp."""

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def check_subtitles_availability(video_id, proxy=None, cookiefile=None):
    """
    Verifica quais tipos de legenda em português (manual e/ou automática)
    estão disponíveis para o vídeo. Retorna um dicionário com booleans.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    available = {"manual": False, "automatic": False}

    command = ["yt-dlp", "--list-subs"]
    if cookiefile and os.path.exists(cookiefile):
        command.extend(["--cookies", cookiefile])
    if proxy:
        command.extend(["--proxy", proxy])
    command.append(url)

    try:
        result = subprocess.check_output(
            command, stderr=subprocess.STDOUT, universal_newlines=True
        )
        output = result.lower()
        if "available subtitles" in output:
            parts = output.split("available subtitles")
            manual_section = (
                parts[1].split("available automatic captions")[0]
                if "available automatic captions" in parts[1]
                else parts[1]
            )
            if "pt" in manual_section or "portuguese" in manual_section:
                available["manual"] = True
        if "available automatic captions" in output:
            auto_section = output.split("available automatic captions")[1]
            if "pt" in auto_section or "portuguese" in auto_section:
                available["automatic"] = True
    except subprocess.CalledProcessError:
        pass

    return available


def setup_video_directories(video_id, output_dir, create_frames_dir=False):
    """Cria a estrutura de pastas isolada para um vídeo específico."""
    base_dir = f"{output_dir}/{video_id}"
    os.makedirs(base_dir, exist_ok=True)
    if create_frames_dir:
        os.makedirs(f"{base_dir}/frames", exist_ok=True)
    return base_dir


def prepare_cookies_file(cookies_dir="."):
    """Localiza cookies_base.txt ou cookies.txt na pasta informada e cria cookies_temp.txt."""
    os.makedirs(cookies_dir, exist_ok=True)
    base_cookie = os.path.join(cookies_dir, "cookies_base.txt")
    standard_cookie = os.path.join(cookies_dir, "cookies.txt")
    temp_cookie = os.path.join(cookies_dir, "cookies_temp.txt")

    if os.path.exists(base_cookie):
        shutil.copy(base_cookie, temp_cookie)
    elif os.path.exists(standard_cookie):
        shutil.copy(standard_cookie, temp_cookie)
    else:
        open(temp_cookie, "w").close()

    return temp_cookie


def _organize_subtitle_files(base_dir, video_id, subs_status):
    """Renomeia os arquivos de legenda baixados para o padrão manual_/automatic_."""
    srt_files = glob.glob(f"{base_dir}/{video_id}*.srt") + glob.glob(
        f"{base_dir}/{video_id}*.vtt"
    )
    for filepath in srt_files:
        if "manual_" in filepath or "automatic_" in filepath:
            continue
        base_filename = os.path.basename(filepath)
        is_auto = "auto" in base_filename.lower() or (
            subs_status["automatic"] and not subs_status["manual"]
        )
        new_name = (
            f"{base_dir}/automatic_{video_id}.srt"
            if is_auto
            else f"{base_dir}/manual_{video_id}.srt"
        )
        if filepath.endswith(".vtt"):
            new_name = new_name.replace(".srt", ".vtt")
        if os.path.exists(new_name):
            os.remove(new_name)
        os.rename(filepath, new_name)


def download_media(
    video_id,
    target_proxy,
    download_audio=True,
    download_subtitles=True,
    download_frames=True,
    download_thumbnail=True,
    output_dir="output",
    cookies_dir=".",
):
    """Baixa seletivamente áudio, legendas, thumbnail e/ou vídeo base conforme parâmetros."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    base_dir = setup_video_directories(
        video_id, output_dir, create_frames_dir=download_frames
    )
    temp_cookie_path = prepare_cookies_file(cookies_dir)

    base_ydl_opts = {
        "outtmpl": f"{base_dir}/%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _SilentLogger(),
        "cookiefile": temp_cookie_path,
        "extractor_args": {"youtube": ["player_client=android"]},
        "remote_components": "ejs:github",
        "retries": 2,
        "socket_timeout": 15,
    }

    if target_proxy:
        base_ydl_opts["proxy"] = target_proxy

    # Legendas
    if download_subtitles:
        subs_status = check_subtitles_availability(
            video_id, target_proxy, cookiefile=temp_cookie_path
        )
        if any(subs_status.values()):
            sub_options = base_ydl_opts.copy()
            sub_options.update({
                "skip_download": True,
                "writesubtitles": subs_status["manual"],
                "writeautomaticsub": subs_status["automatic"],
                "subtitleslangs": ["pt"],
                "subtitlesformat": "srt",
            })
            with yt_dlp.YoutubeDL(sub_options) as ydl:
                ydl.download([url])
            _organize_subtitle_files(base_dir, video_id, subs_status)

    # Thumbnail
    if download_thumbnail:
        thumb_options = base_ydl_opts.copy()
        thumb_options.update({
            "skip_download": True,
            "writethumbnail": True,
        })
        with yt_dlp.YoutubeDL(thumb_options) as ydl:
            ydl.download([url])

    # Áudio
    if download_audio:
        audio_options = base_ydl_opts.copy()
        audio_options.update({
            "format": "ba/bestaudio/b",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
        with yt_dlp.YoutubeDL(audio_options) as ydl:
            ydl.download([url])

    # Vídeo base -> frames
    if download_frames:
        video_options = base_ydl_opts.copy()
        video_options.update({
            "format": "bv/bestvideo/b",
        })
        with yt_dlp.YoutubeDL(video_options) as ydl:
            ydl.download([url])


def extract_frames(video_id, output_dir="output", target_fps="1/10"):
    """Encontra dinamicamente o arquivo de vídeo baixado e extrai os frames."""
    base_dir = f"{output_dir}/{video_id}"
    frames_dir = f"{base_dir}/frames"
    output_pattern = f"{frames_dir}/frame_%04d.jpg"
    os.makedirs(frames_dir, exist_ok=True)
    files_in_folder = glob.glob(f"{base_dir}/{video_id}.*")
    video_path = None

    for filepath in files_in_folder:
        if not filepath.endswith(
            (".mp3", ".srt", ".vtt", ".jpg", ".m4a", ".webp", ".png")
        ):
            video_path = filepath
            break

    if not video_path:
        return
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        video_path,
        "-vf",
        f"fps={target_fps}",
        "-q:v",
        "2",
        output_pattern,
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        os.remove(video_path)
    except subprocess.CalledProcessError:
        pass


def process_video(
    video_id,
    download_audio=True,
    download_subtitles=True,
    download_frames=True,
    download_thumbnail=True,
    output_dir="output",
    cookies_dir=".",
    use_proxies=False,
    proxy_list=None,
):
    """Função orquestradora que retorna 'SUCCESS', 'UNAVAILABLE', 'BOT_BLOCK',
    'SESSION_BLOCK' ou 'ERROR'."""
    global current_proxy_index
    current_proxy_index = load_proxy_index(cookies_dir)
    last_status = "BOT_BLOCK"

    if use_proxies and proxy_list:
        available_networks = proxy_list
    else:
        available_networks = [None]

    remaining_attempts = len(available_networks)

    while remaining_attempts > 0:
        safe_index = current_proxy_index % len(available_networks)
        target_proxy = available_networks[safe_index]
        network_name = "Server Direct" if target_proxy is None else target_proxy

        try:
            download_media(
                video_id=video_id,
                target_proxy=target_proxy,
                download_audio=download_audio,
                download_subtitles=download_subtitles,
                download_frames=download_frames,
                download_thumbnail=download_thumbnail,
                output_dir=output_dir,
                cookies_dir=cookies_dir,
            )
            if download_frames:
                extract_frames(video_id, output_dir)
            return "SUCCESS"

        except Exception as e:
            error_str = str(e).lower()

            # Único sinal confiável de IP bloqueado/sinalizado pelo YouTube.
            # HTTP 429 (ex.: legendas) e rate-limit de sessão NÃO indicam IP bloqueado.
            ip_block_indicators = (
                "sign in to confirm you're not a bot",
                "sign in to confirm you’re not a bot",
            )

            if any(indicator in error_str for indicator in ip_block_indicators):
                print(
                    f"[{video_id}] Bloqueio/Rate-limit detectado na rede '{network_name}'."
                )
                last_status = "BOT_BLOCK"
                current_proxy_index = (current_proxy_index + 1) % len(
                    available_networks
                )
                save_proxy_index(cookies_dir, current_proxy_index)
                remaining_attempts -= 1

                if remaining_attempts > 0:
                    next_target = available_networks[
                        current_proxy_index % len(available_networks)
                    ]
                    next_name = (
                        "Conexao Direta" if next_target is None else next_target
                    )
                    print(
                        f"[{video_id}] Roteando trafego para a nova origem:"
                        f" '{next_name}'."
                    )
                continue

            # Rate-limit de sessão (cookie/conta): não é bloqueio de IP, então
            # trocar de proxy não resolve. Precisa vir antes de "unavailable",
            # pois a mensagem do YouTube contém "video unavailable" e o vídeo
            # seria descartado por engano.
            if "rate-limited by youtube" in error_str:
                print(
                    f"[{video_id}] Rate-limit de sessao (cookie) detectado."
                    " Nao e bloqueio de IP."
                )
                return "SESSION_BLOCK"

            # 429 pontual (ex.: legendas): erro transitório, não é bloqueio.
            rate_limit_indicators = (
                "http error 429",
                "too many requests",
            )

            if any(indicator in error_str for indicator in rate_limit_indicators):
                print(
                    f"[{video_id}] Erro no processamento (rate-limit, nao e"
                    f" bloqueio de IP): {error_str}"
                )
                return "ERROR"

            unavailable_indicators = (
                "video unavailable",
                "this video is not available",
                "this video is unavailable",
                "private video",
                "this video is private",
                "video has been removed",
                "account associated with this video has been terminated",
                "join this channel to get access",
                "members-only content",
            )

            if any(
                indicator in error_str for indicator in unavailable_indicators
            ):
                shutil.rmtree(f"{output_dir}/{video_id}", ignore_errors=True)
                print(
                    f"[{video_id}] Video indisponivel ou privado. Pulando..."
                )
                return "UNAVAILABLE"

            # Erro desconhecido (ex.: timeout no googlevideo.com): pode ser
            # problema da rede/proxy atual, então tenta a próxima antes de desistir.
            print(
                f"[{video_id}] Erro no processamento ({network_name}): {e!r}"
            )
            last_status = "ERROR"
            current_proxy_index = (current_proxy_index + 1) % len(
                available_networks
            )
            save_proxy_index(cookies_dir, current_proxy_index)
            remaining_attempts -= 1
            continue

    if last_status == "BOT_BLOCK":
        print(
            f"[{video_id}] Falha critica: todas as conexoes falharam por"
            " bloqueio."
        )
    return last_status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multimodal YouTube Extractor")
    parser.add_argument("--id", type=str, required=True, help="Unique Video ID")
    parser.add_argument(
        "--output", type=str, help="Main output folder", default="output"
    )
    parser.add_argument(
        "--cookies-dir",
        type=str,
        help="Directory containing cookies_base.txt or cookies.txt",
        default=".",
    )

    # Flags de seleção modular
    parser.add_argument(
        "--audio", action="store_true", help="Download audio (.mp3)"
    )
    parser.add_argument(
        "--subtitles",
        "--subs",
        dest="subtitles",
        action="store_true",
        help="Download .srt/.vtt subtitles",
    )
    parser.add_argument(
        "--frames", action="store_true", help="Download video and extract frames"
    )
    parser.add_argument(
        "--thumbnail",
        "--thumb",
        dest="thumbnail",
        action="store_true",
        help="Download video thumbnail",
    )

    # Flags de rede / proxy
    parser.add_argument(
        "--use-proxies",
        action="store_true",
        help="Enable proxy rotation using --proxies",
    )
    parser.add_argument(
        "--proxies",
        type=str,
        default="",
        help="Comma-separated list of proxy URLs (e.g., socks5://127.0.0.1:1080)",
    )

    args = parser.parse_args()

    # se nenhuma flag específica for informada, ativa todas por padrão
    if not (args.audio or args.subtitles or args.frames or args.thumbnail):
        dl_audio = True
        dl_subtitles = True
        dl_frames = True
        dl_thumbnail = True
    else:
        dl_audio = args.audio
        dl_subtitles = args.subtitles
        dl_frames = args.frames
        dl_thumbnail = args.thumbnail

    proxy_list = (
        [p.strip() for p in args.proxies.split(",") if p.strip()]
        if args.proxies
        else []
    )

    status = process_video(
        video_id=args.id,
        download_audio=dl_audio,
        download_subtitles=dl_subtitles,
        download_frames=dl_frames,
        download_thumbnail=dl_thumbnail,
        output_dir=args.output,
        cookies_dir=args.cookies_dir,
        use_proxies=args.use_proxies,
        proxy_list=proxy_list,
    )

    if status == "UNAVAILABLE":
        sys.exit(2)
    elif status == "SESSION_BLOCK":
        sys.exit(3)
    elif status != "SUCCESS":
        sys.exit(1)
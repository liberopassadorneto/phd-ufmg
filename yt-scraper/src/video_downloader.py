import argparse
import glob
import os
import shutil
import subprocess
import sys
import yt_dlp

current_proxy_index = 0

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


def is_already_processed(
    video_id,
    output_dir,
    download_audio=True,
    download_subtitles=True,
    download_frames=True,
    download_thumbnail=True,
):
    """Verifica se todos os artefatos solicitados já existem localmente."""
    base_dir = f"{output_dir}/{video_id}"
    if not os.path.exists(base_dir):
        return False

    if download_frames:
        frames_dir = f"{base_dir}/frames"
        if not (os.path.exists(frames_dir) and len(os.listdir(frames_dir)) > 0):
            return False

    if download_audio:
        if not os.path.exists(f"{base_dir}/{video_id}.mp3"):
            return False

    if download_subtitles:
        subs = glob.glob(f"{base_dir}/*{video_id}*.srt") + glob.glob(
            f"{base_dir}/*{video_id}*.vtt"
        )
        if not subs:
            return False

    if download_thumbnail:
        thumbs = (
            glob.glob(f"{base_dir}/{video_id}.jpg")
            + glob.glob(f"{base_dir}/{video_id}.webp")
            + glob.glob(f"{base_dir}/{video_id}.png")
        )
        if not thumbs:
            return False

    return True


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
        "cookiefile": temp_cookie_path,
        "extractor_args": {"youtube": ["player_client=android"]},
        "remote_components": "ejs:github",
    }

    if target_proxy:
        base_ydl_opts["proxy"] = target_proxy

    # download das legendas
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

    # download da thumbnail
    if download_thumbnail:
        thumb_options = base_ydl_opts.copy()
        thumb_options.update({
            "skip_download": True,
            "writethumbnail": True,
        })
        with yt_dlp.YoutubeDL(thumb_options) as ydl:
            ydl.download([url])

    # download do áudio
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

    # download do vídeo base -> frames
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
    """Função orquestradora que retorna o status do download ('SUCCESS', 'BOT_BLOCK' ou 'ERROR')."""
    global current_proxy_index

    if is_already_processed(
        video_id,
        output_dir,
        download_audio,
        download_subtitles,
        download_frames,
        download_thumbnail,
    ):
        print(f"\n--- [SKIPPING] Video already processed: {video_id} ---")
        return "SUCCESS"

    selected_tasks = [
        name
        for name, enabled in [
            ("audio", download_audio),
            ("subtitles", download_subtitles),
            ("frames", download_frames),
            ("thumbnail", download_thumbnail),
        ]
        if enabled
    ]
    print(
        f"\n--- Starting processing: {video_id} [{', '.join(selected_tasks)}]"
        " ---"
    )

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

            if (
                "sign in to confirm" in error_str
                or "bot" in error_str
                or "cookies" in error_str
            ):
                print(
                    f"[{video_id}] bloqueio detectado na rede `{network_name}`."
                    ">> iniciando rotação de IP."
                )
                current_proxy_index = (current_proxy_index + 1) % len(
                    available_networks
                )
                remaining_attempts -= 1

                next_target = available_networks[
                    current_proxy_index % len(available_networks)
                ]
                next_name = (
                    "conexão direta" if next_target is None else next_target
                )
                print(
                    f"[{video_id}] >> Roteando tráfego para a nova origem:"
                    f" `{next_name}`."
                )
            else:
                print(f"[{video_id}] Failed to process: {error_str}")
                return "ERROR"

    print(
        f"[{video_id}] falha crítica. Todas as conexões falharam por bloqueio."
    )
    return "BOT_BLOCK"


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

    # flags de seleção modular
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

    status = process_video(
        video_id=args.id,
        download_audio=dl_audio,
        download_subtitles=dl_subtitles,
        download_frames=dl_frames,
        download_thumbnail=dl_thumbnail,
        output_dir=args.output,
        cookies_dir=args.cookies_dir,
    )

    if status != "SUCCESS":
        sys.exit(1)
import os
import sys
import csv
import argparse
import yt_dlp
import subprocess
import glob
import shutil
import requests

current_proxy_index = 0

def send_telegram_alert(text, bot_token, chat_id):
    """Notifica o Telegram sobre eventos de rede com baixa verbosidade visual."""
    if not bot_token or not chat_id or bot_token == "SEU_BOT_TOKEN_AQUI":
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def check_subtitles_availability(video_id, proxy=None):
    """
    Verifica quais tipos de legenda em português (manual e/ou automática) 
    estão disponíveis para o vídeo. Retorna um dicionário com booleans.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    available = {"manual": False, "automatic": False}
    
    command = ["yt-dlp", "--list-subs"]
    if proxy:
        command.extend(["--proxy", proxy])
    command.append(url)
    
    try:
        result = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
        output = result.lower()
        if "available subtitles" in output:
            parts = output.split("available subtitles")
            manual_section = parts[1].split("available automatic captions")[0] if "available automatic captions" in parts[1] else parts[1]
            if "pt" in manual_section or "portuguese" in manual_section:
                available["manual"] = True
        if "available automatic captions" in output:
            auto_section = output.split("available automatic captions")[1]
            if "pt" in auto_section or "portuguese" in auto_section:
                available["automatic"] = True
    except subprocess.CalledProcessError:
        pass
    
    return available

def setup_video_directories(video_id, output_dir):
    """Cria a estrutura de pastas isolada para um vídeo específico."""
    base_dir = f"{output_dir}/{video_id}"
    os.makedirs(f"{base_dir}/frames", exist_ok=True)
    return base_dir

def download_media(video_id, target_proxy, extract_subs=False, output_dir="output"):
    """Baixa o áudio, vídeo base e gerencia o download de ambas as legendas."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    base_dir = setup_video_directories(video_id, output_dir)
    
    if os.path.exists('cookies_base.txt'):
        shutil.copy('cookies_base.txt', 'cookies_temp.txt')
    elif os.path.exists('cookies.txt'):
        shutil.copy('cookies.txt', 'cookies_temp.txt')
    else:
        open('cookies_temp.txt', 'w').close()
    
    subs_status = {"manual": False, "automatic": False}
    if extract_subs:
        subs_status = check_subtitles_availability(video_id, target_proxy)

    audio_options = {
        'format': 'ba/bestaudio/b', 
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': f'{base_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies_temp.txt',
        'extractor_args': {'youtube': ['player_client=android']}, 
        'writethumbnail': True,
        'remote_components': 'ejs:github'
    }

    video_options = {
        'format': 'bv/bestvideo/b',
        'outtmpl': f'{base_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'cookiefile': 'cookies_temp.txt', 
        'extractor_args': {'youtube': ['player_client=android']},
        'remote_components': 'ejs:github'
    }

    if target_proxy:
        audio_options['proxy'] = target_proxy
        video_options['proxy'] = target_proxy

    if extract_subs and any(subs_status.values()):
        audio_options.update({
            'writesubtitles': subs_status["manual"],
            'writeautomaticsub': subs_status["automatic"],
            'subtitleslangs': ['pt'],
            'subtitlesformat': 'srt',
        })

    with yt_dlp.YoutubeDL(audio_options) as ydl:
        ydl.download([url])
        srt_files = glob.glob(f"{base_dir}/{video_id}*.srt") + glob.glob(f"{base_dir}/{video_id}*.vtt")
        for filepath in srt_files:
            if "manual_" in filepath or "automatic_" in filepath: continue
            base_filename = os.path.basename(filepath)
            new_name = f"{base_dir}/automatic_{video_id}.srt" if "auto" in base_filename.lower() or (subs_status["automatic"] and not subs_status["manual"]) else f"{base_dir}/manual_{video_id}.srt"
            if filepath.endswith('.vtt'): new_name = new_name.replace('.srt', '.vtt')
            if os.path.exists(new_name): os.remove(new_name)
            os.rename(filepath, new_name)

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
        if not filepath.endswith(('.mp3', '.srt', '.vtt', '.jpg', '.m4a', '.webp')):
            video_path = filepath
            break

    if not video_path: return
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", video_path, "-vf", f"fps={target_fps}", "-q:v", "2", output_pattern]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        os.remove(video_path)
    except subprocess.CalledProcessError:
        pass

def process_video(video_id, extract_subs, output_dir, bot_token=None, chat_id=None, use_proxies=False, proxy_list=None):
    """Função orquestradora que retorna o status do download."""
    global current_proxy_index
    frames_dir = f"{output_dir}/{video_id}/frames"
    
    if os.path.exists(frames_dir) and len(os.listdir(frames_dir)) > 0:
        print(f"\n--- [SKIPPING] Video already processed: {video_id} ---")
        return "SUCCESS" 

    print(f"\n--- Starting processing: {video_id} ---")
    
    if use_proxies and proxy_list:
        available_networks = [None] + proxy_list
    else:
        available_networks = [None]

    remaining_attempts = len(available_networks)
    
    while remaining_attempts > 0:
        safe_index = current_proxy_index % len(available_networks)
        target_proxy = available_networks[safe_index]
        network_name = "Server Direct" if target_proxy is None else target_proxy
        
        try:
            download_media(video_id, target_proxy, extract_subs, output_dir)
            extract_frames(video_id, output_dir)
            return "SUCCESS"
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "sign in to confirm" in error_str or "bot" in error_str or "cookies" in error_str:
                msg_alert = (
                    f"⚠️ Bloqueio detectado no vídeo `{video_id}`\n"
                    f"- Rede bloqueada: `{network_name}`\n"
                    f"- Etapa: Início de rotação de IP."
                )
                print(f"[{video_id}] {msg_alert}")
                send_telegram_alert(msg_alert, bot_token, chat_id)
                
                current_proxy_index = (current_proxy_index + 1) % len(available_networks)
                remaining_attempts -= 1
                
                next_target = available_networks[current_proxy_index % len(available_networks)]
                next_name = "Conexão Direta" if next_target is None else next_target
                msg_transition = f"🔄 Roteando tráfego de extração para a nova origem: `{next_name}`."
                print(f"[{video_id}] {msg_transition}")
                send_telegram_alert(msg_transition, bot_token, chat_id)
            else:
                print(f"[{video_id}] Failed to process: {error_str}")
                return "ERROR"
                
    msg_fatal = f"🚫 Falha crítica. Todos os túneis SSH e conexões locais falharam no vídeo `{video_id}`."
    print(msg_fatal)
    send_telegram_alert(msg_fatal, bot_token, chat_id)
    return "BOT_BLOCK"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multimodal YouTube Extractor")
    parser.add_argument("--id", type=str, help="Unique Video ID")
    parser.add_argument("--csv", type=str, help="Path to CSV file")
    parser.add_argument("--limit", type=int, help="Maximum number of videos to process", default=None)
    parser.add_argument("--subs", action="store_true", help="Also download .srt subtitles")
    parser.add_argument("--output", type=str, help="Main output folder", default="output")
    
    args = parser.parse_args()
 
    if args.id:
        process_video(args.id, args.subs, args.output)
        
    elif args.csv:
        if not os.path.exists(args.csv):
            print(f"Error: The file {args.csv} was not found.")
            sys.exit(1)
            
        print(f"Reading database: {args.csv}")
        with open(args.csv, mode='r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file, delimiter=',') 
            headers = reader.fieldnames
            rows = list(reader)

        pending_videos = rows.copy()
        processed_videos = 0
        block_detected = False

        for row in rows:
            if args.limit and processed_videos >= args.limit:
                break
                
            video_id = row.get('Video_id') or row.get('video_id')
            if video_id:
                status = process_video(video_id, args.subs, args.output)
                
                if status == "BOT_BLOCK":
                    print(f"\n[ALERT] YouTube block detected on video {video_id}.")
                    block_detected = True
                    break 
                elif status == "SUCCESS":
                    processed_videos += 1
                    pending_videos.remove(row) 
                    
        print(f"\nUpdating file {args.csv}...")
        with open(args.csv, mode='w', encoding='utf-8', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(pending_videos)
            
        print(f"CSV saved. {len(pending_videos)} videos remaining for next runs.")
        
        if block_detected:
            print("Program terminated preventively due to network block.")
            sys.exit(1)
                    
    else:
        parser.print_help()
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import configparser
import csv
from datetime import datetime, timedelta
import glob
import math
import os
import shutil
import subprocess
import sys
import time
import requests
from storage_sync import StorageSyncManager, TranscriptRecord


def load_configuration(conf_path):
    """Lê e valida o arquivo de configuração .conf."""
    if not os.path.exists(conf_path):
        print(f"Error: Configuration file '{conf_path}' not found.")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(conf_path, encoding="utf-8")
    return config


def send_telegram_message(text, bot_token, chat_id):
    """Envia uma mensagem de texto para o Telegram."""
    if not bot_token or bot_token == "SEU_BOT_TOKEN_AQUI":
        print("[Telegram Warning] Token not configured. Message ignored.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[Telegram Error] Failed to send message: {e}")
        return False


def load_and_filter_csv(csv_path, synced_ids: set[str]):
    """Lê o CSV original e remove os IDs que já constam como sincronizados no Postgres."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    pending_rows = []
    already_processed = 0

    for row in rows:
        vid = row.get("Video_id") or row.get("video_id")
        if vid and str(vid).strip() in synced_ids:
            already_processed += 1
        else:
            pending_rows.append(row)

    original_total = len(rows)
    print(
        f"[Step 1] Original total: {original_total} | Already synced in DB:"
        f" {already_processed} | Pending: {len(pending_rows)}"
    )

    pending_csv_path = "csv_pending_execution.csv"
    with open(pending_csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pending_rows)

    return (
        pending_csv_path,
        pending_rows,
        fieldnames,
        original_total,
        already_processed,
    )


def build_downloader_cli_args(
    downloader_script: str,
    video_id: str,
    output_dir: str,
    cookies_dir: str,
    download_opts: dict,
    use_proxies: bool = False,
    raw_proxies: str = "",
) -> list[str]:
    """Monta o comando CLI com os argumentos modulares e proxies para o video_downloader.py."""
    cmd = [
        sys.executable,
        downloader_script,
        "--id",
        str(video_id),
        "--output",
        output_dir,
        "--cookies-dir",
        cookies_dir,
    ]
    if download_opts.get("audio"):
        cmd.append("--audio")
    if download_opts.get("subtitles"):
        cmd.append("--subtitles")
    if download_opts.get("frames"):
        cmd.append("--frames")
    if download_opts.get("thumbnail"):
        cmd.append("--thumbnail")
    if use_proxies and raw_proxies:
        cmd.append("--use-proxies")
        cmd.extend(["--proxies", raw_proxies])
    return cmd


def resolve_downloaded_modality_label(download_opts: dict) -> str:
    """
    Gera a string padronizada (<= 20 chars) para a coluna file_format
    com base nas flags ativas no config.conf.
    """
    tags = []
    if download_opts.get("audio"):
        tags.append("AUDIO")
    if download_opts.get("frames"):
        tags.append("FRAMES")
    if download_opts.get("subtitles"):
        tags.append("SUBS")
    if download_opts.get("thumbnail"):
        tags.append("THUMB")
    return ",".join(tags) if tags else "UNKNOWN"


def persist_and_cleanup_video(
    sync_manager: StorageSyncManager,
    video_id: str,
    abs_output_dir: str,
    download_opts: dict,
) -> None:
    """
    1. Envia dados brutos do vídeo para o bucket S3.
    2. Registra metadados na tabela phd_pipeline.transcript no Postgres.
    3. Exclui a pasta local de dados brutos do vídeo.
    """
    video_folder = os.path.join(abs_output_dir, str(video_id))
    if not os.path.exists(video_folder):
        return

    # salva os dados no bucket
    uploaded_assets = sync_manager.upload_video_assets_to_s3(
        youtube_video_id=str(video_id),
        video_folder=video_folder,
    )

    if not uploaded_assets:
        shutil.rmtree(video_folder, ignore_errors=True)
        return

    modality_str = resolve_downloaded_modality_label(download_opts)
    total_size_bytes = sum(a["size_bytes"] for a in uploaded_assets)

    # verifica se há arquivos de legenda entre os uploads para definir source_type e s3_key
    subtitle_assets = [
        a
        for a in uploaded_assets
        if a["filename"].lower().endswith((".srt", ".vtt"))
    ]

    # verificacoes para adicao no banco postgres
    if subtitle_assets:
        for asset in subtitle_assets:
            source_type = (
                "YOUTUBE_MANUAL"
                if asset["filename"].lower().startswith("manual_")
                else "YOUTUBE_AUTOMATIC"
            )
            record = TranscriptRecord(
                youtube_video_id=str(video_id),
                source_type=source_type,
                language_code="pt",
                file_format=modality_str,
                s3_bucket=asset["s3_bucket"],
                s3_key=asset["s3_key"],
                size_bytes=asset["size_bytes"],
            )
            sync_manager.save_transcript_to_db(record)
    else:
        # caso tenha baixado apenas AUDIO / FRAMES / THUMB (sem legendas)
        primary_asset = uploaded_assets[0]
        s3_key_ref = (
            f"data/{video_id}/frames/"
            if download_opts.get("frames") and not download_opts.get("audio")
            else primary_asset["s3_key"]
        )
        record = TranscriptRecord(
            youtube_video_id=str(video_id),
            source_type="YOUTUBE_AUTOMATIC",
            language_code="pt",
            file_format=modality_str,
            s3_bucket=primary_asset["s3_bucket"],
            s3_key=s3_key_ref,
            size_bytes=total_size_bytes,
        )
        sync_manager.save_transcript_to_db(record)

    # exclui dados brutos locais após confirmação no S3 e Postgres
    shutil.rmtree(video_folder, ignore_errors=True)


def worker_process(
    profile_id,
    csv_slice,
    cookie_path,
    output_dir,
    download_opts,
    use_proxies,
    raw_proxies,
    pg_config,
    s3_config,
    bot_token,
    chat_id,
):
    """Executado isoladamente em paralelo para cada cookie."""
    start_time = time.time()
    work_dir = os.path.abspath(f"worker_env_profile_{profile_id}")
    os.makedirs(work_dir, exist_ok=True)

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        source_downloader = os.path.join(script_dir, "video_downloader.py")

        shutil.copy(cookie_path, os.path.join(work_dir, "cookies_base.txt"))
        downloader_copy = os.path.join(work_dir, "video_downloader.py")
        shutil.copy(source_downloader, downloader_copy)
        sync_manager = StorageSyncManager(
            pg_config=pg_config, s3_config=s3_config
        )

        with open(csv_slice["path"], mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            rows = list(reader)

        pending_videos = rows.copy()
        extracted_videos = 0
        block_detected = False
        cookie_name = os.path.basename(cookie_path)
        abs_output_dir = os.path.abspath(output_dir)

        for row in rows:
            video_id = row.get("Video_id") or row.get("video_id")
            if not video_id:
                continue

            cmd = build_downloader_cli_args(
                downloader_script=downloader_copy,
                video_id=video_id,
                output_dir=abs_output_dir,
                cookies_dir=work_dir,
                download_opts=download_opts,
                use_proxies=use_proxies,
                raw_proxies=raw_proxies,
            )

            proc = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
            )

            combined_output = f"{proc.stdout}\n{proc.stderr}"
            print(combined_output.strip())

            if proc.returncode == 0:
                try:
                    persist_and_cleanup_video(
                        sync_manager=sync_manager,
                        video_id=video_id,
                        abs_output_dir=abs_output_dir,
                        download_opts=download_opts,
                    )
                    extracted_videos += 1
                    if row in pending_videos:
                        pending_videos.remove(row)
                except Exception as sync_err:
                    print(
                        f"[Sync Error] Falha ao salvar vídeo {video_id} no"
                        f" S3/DB: {sync_err}"
                    )
            else:
                if (
                    "bloqueio detectado" in combined_output.lower()
                    or "falha crítica" in combined_output.lower()
                ):
                    block_detected = True
                    block_msg = (
                        f"⚠️ *Bloqueio Detectado (Perfil {profile_id})*\n"
                        f"- Cookie: `{cookie_name}`\n"
                        f"- Vídeo: `{video_id}`\n"
                        "- Ação: Worker encerrado preventivamente."
                    )
                    send_telegram_message(block_msg, bot_token, chat_id)
                    break

        total_time = time.time() - start_time
        formatted_time = str(timedelta(seconds=int(total_time)))

        os.makedirs("relatorios", exist_ok=True)
        report_path = os.path.join(
            "relatorios", f"relatorio_perfil_{profile_id}.txt"
        )

        report_content = (
            f"========================================\n"
            f"RELATÓRIO DE EXTRAÇÃO - PERFIL {profile_id}\n"
            f"========================================\n"
            f"Arquivo de Cookie: {cookie_name}\n"
            f"Total de Vídeos Alocados: {len(rows)}\n"
            f"Vídeos Extraídos e Sincronizados: {extracted_videos}\n"
            f"Vídeos Pendentes/Restantes: {len(pending_videos)}\n"
            f"Status Final: {'BLOQUEADO (Bot Block)' if block_detected else 'CONCLUÍDO'}\n"
            f"Tempo de Execução: {formatted_time}\n"
            f"========================================\n"
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        telegram_msg = (
            f"*Relatório do Perfil {profile_id}*\n\n"
            f"*Cookie:* `{cookie_name}`\n"
            f"*Sincronizados (S3 + DB):* {extracted_videos}/{len(rows)}\n"
            f"*Pendentes:* {len(pending_videos)}\n"
            f"*Tempo:* {formatted_time}\n"
            f"*Status:* {'🚫 Bloqueado pelo YouTube' if block_detected else '✅ Finalizado com Sucesso'}"
        )
        send_telegram_message(telegram_msg, bot_token, chat_id)

        return {
            "profile_id": profile_id,
            "extracted": extracted_videos,
            "pending": pending_videos,
            "blocked": block_detected,
            "time": total_time,
            "fieldnames": headers,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Parallel Extractor Orchestrator with .conf file"
    )
    parser.add_argument(
        "--conf",
        type=str,
        default="config.conf",
        help="Path to .conf configuration file",
    )
    args = parser.parse_args()

    config = load_configuration(args.conf)

    # Seção DEFAULT
    cookies_dir = config.get("DEFAULT", "cookies_dir", fallback="cookies")
    output_dir = config.get("DEFAULT", "output_dir", fallback="output")
    target_csv = config.get("DEFAULT", "csv_alvo", fallback="lista_alvos.csv")

    dl_audio = config.getboolean("DEFAULT", "extrair_audio", fallback=False)
    dl_subs = config.getboolean("DEFAULT", "extrair_subs", fallback=False)
    dl_frames = config.getboolean("DEFAULT", "extrair_frames", fallback=False)
    dl_thumb = config.getboolean("DEFAULT", "extrair_thumb", fallback=False)

    if not (dl_audio or dl_subs or dl_frames or dl_thumb):
        dl_audio = dl_subs = dl_frames = dl_thumb = True

    download_opts = {
        "audio": dl_audio,
        "subtitles": dl_subs,
        "frames": dl_frames,
        "thumbnail": dl_thumb,
    }
    active_modules = [k for k, v in download_opts.items() if v]

    # Configurações de proxy
    use_proxies = config.getboolean("DEFAULT", "using_proxy", fallback=False)
    raw_proxies = config.get("DEFAULT", "proxies_list", fallback="").strip()

    # Seção S3
    s3_config = {
        "endpoint": config.get("S3", "endpoint"),
        "port": config.get("S3", "port", fallback=None),
        "access_key": config.get("S3", "access_key"),
        "secret_key": config.get("S3", "secret_key"),
        "bucket_name": config.get("S3", "bucket_name"),
    }

    # Seção POSTGRES
    pg_config = {
        "host": config.get("POSTGRES", "host"),
        "port": config.getint("POSTGRES", "port", fallback=5432),
        "dbname": config.get("POSTGRES", "dbname"),
        "user": config.get("POSTGRES", "user"),
        "password": config.get("POSTGRES", "password"),
    }

    # Seção TELEGRAM
    bot_token = config.get("TELEGRAM", "bot_token", fallback="")
    chat_id = config.get("TELEGRAM", "chat_id", fallback="")

    global_start = time.time()

    cookie_files = sorted(glob.glob(os.path.join(cookies_dir, "*.txt")))
    if not cookie_files:
        print(f"Error: No .txt cookie file found in '{cookies_dir}'.")
        sys.exit(1)

    print(f"Found {len(cookie_files)} cookies for processing.")
    print(f"Enabled extraction modules: {', '.join(active_modules)}")
    if use_proxies and raw_proxies:
        print(f"Proxy rotation enabled: {raw_proxies}")

    # consulta vídeos já registrados no Postgres para filtrar o CSV
    root_sync = StorageSyncManager(pg_config=pg_config, s3_config=s3_config)
    synced_ids = root_sync.get_already_synced_youtube_ids()

    (
        filtered_csv_path,
        pending_records,
        headers,
        original_total,
        already_processed,
    ) = load_and_filter_csv(target_csv, synced_ids)

    if not pending_records:
        print("All videos from the CSV have already been synced. Exiting.")
        send_telegram_message(
            "ℹ️ *Aviso:* Todos os vídeos do CSV informado já foram processados"
            " e sincronizados anteriormente.",
            bot_token,
            chat_id,
        )
        sys.exit(0)

    num_cookies = len(cookie_files)
    slice_size = math.ceil(len(pending_records) / num_cookies)
    slices = [
        pending_records[i : i + slice_size]
        for i in range(0, len(pending_records), slice_size)
    ]

    sub_csv_files = []
    os.makedirs("sub_csvs", exist_ok=True)

    for idx, current_slice in enumerate(slices):
        sub_path = os.path.join("sub_csvs", f"sub_{idx + 1}.csv")
        with open(sub_path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(current_slice)
        sub_csv_files.append({"path": sub_path, "quantity": len(current_slice)})

    proxy_status_str = (
        f"Ativo ({raw_proxies})" if (use_proxies and raw_proxies) else "Direto"
    )
    start_msg = (
        f"*INICIANDO NOVO CICLO DE EXTRAÇÃO*\n\n"
        f"*Módulos Ativos:* `{', '.join(active_modules)}`\n"
        f"*Rede/Proxies:* `{proxy_status_str}`\n"
        f"*Total no CSV Alvo:* {original_total}\n"
        f"*Já Sincronizados no DB:* {already_processed}\n"
        f"*Faltam Processar:* {len(pending_records)}\n"
        f"*Perfis/Cookies Ativos:* {num_cookies}\n"
        f"*Média por Perfil:* ~{slice_size} vídeos\n\n"
        " _Fluxo ativo: Download → S3 → Postgres → Limpeza local por vídeo._"
    )
    send_telegram_message(start_msg, bot_token, chat_id)

    results = []
    with ProcessPoolExecutor(max_workers=num_cookies) as executor:
        futures = []
        for i, cookie_file in enumerate(cookie_files):
            if i < len(sub_csv_files):
                profile_id = i + 1
                f = executor.submit(
                    worker_process,
                    profile_id,
                    sub_csv_files[i],
                    cookie_file,
                    output_dir,
                    download_opts,
                    use_proxies,
                    raw_proxies,
                    pg_config,
                    s3_config,
                    bot_token,
                    chat_id,
                )
                futures.append(f)

        for future in as_completed(futures):
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                print(f"[Processing Error] Failure in execution profile: {e}")

    all_unextracted = []
    total_extracted = 0
    total_blocks = 0

    for res in results:
        total_extracted += res["extracted"]
        all_unextracted.extend(res["pending"])
        if res["blocked"]:
            total_blocks += 1

    final_pending_csv = "csv_not_extracted_final.csv"
    with open(final_pending_csv, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_unextracted)

    final_reports_dir = "relatorios_consolidados"
    os.makedirs(final_reports_dir, exist_ok=True)

    for report_file in glob.glob("relatorios/relatorio_perfil_*.txt"):
        shutil.move(
            report_file,
            os.path.join(final_reports_dir, os.path.basename(report_file)),
        )

    overall_total_time = str(timedelta(seconds=int(time.time() - global_start)))

    general_report_path = os.path.join(
        final_reports_dir, "RESUMO_GERAL_EXECUCAO.txt"
    )
    summary_text = (
        f"========================================\n"
        f"RESUMO DE EXECUÇÃO PARALELA\n"
        f"========================================\n"
        f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Módulos extraídos: {', '.join(active_modules)}\n"
        f"Perfis de cookies utilizados: {num_cookies}\n"
        f"Total de vídeos sincronizados nesta sessão: {total_extracted}\n"
        f"Total de vídeos que ainda faltam: {len(all_unextracted)}\n"
        f"Contas/Cookies que sofreram bloqueio: {total_blocks}\n"
        f"Tempo total decorrido: {overall_total_time}\n"
        f"========================================\n"
    )
    with open(general_report_path, "w", encoding="utf-8") as f:
        f.write(summary_text)

    shutil.rmtree("sub_csvs", ignore_errors=True)
    if os.path.exists("relatorios"):
        shutil.rmtree("relatorios", ignore_errors=True)
    if os.path.exists(filtered_csv_path):
        os.remove(filtered_csv_path)

    final_msg = (
        f"*EXECUÇÃO PARALELA FINALIZADA*\n\n"
        f"*Módulos:* `{', '.join(active_modules)}`\n"
        f"*Total Sincronizados Nesta Sessão:* {total_extracted}\n"
        f"*Ainda Pendentes:* {len(all_unextracted)}\n"
        f"*Contas Bloqueadas:* {total_blocks}/{num_cookies}\n"
        f"*Tempo Total:* {overall_total_time}\n\n"
        "Os relatórios individuais e o resumo geral foram salvos na pasta"
        f" `{final_reports_dir}/`.\n"
        f"O CSV final com as pendências foi atualizado em `{final_pending_csv}`."
    )
    send_telegram_message(final_msg, bot_token, chat_id)
    print("\nExecution and final consolidation completed successfully!")


if __name__ == "__main__":
    main()
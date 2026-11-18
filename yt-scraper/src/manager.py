import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import configparser
import csv
from datetime import datetime, timedelta
import glob
import math
import os
import random
import shutil
import subprocess
import sys
import time
import requests
from storage_sync import StorageSyncManager, TranscriptRecord


def load_configuration(conf_path):
    """Lê e valida o arquivo de configuração .conf."""
    if not os.path.exists(conf_path):
        print(f"[ERRO] Arquivo de configuracao '{conf_path}' nao encontrado.")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(conf_path, encoding="utf-8")
    return config


def send_telegram_message(text, bot_token, chat_id):
    """Envia uma mensagem de texto para o Telegram."""
    if not bot_token or bot_token == "SEU_BOT_TOKEN_AQUI":
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM][ERRO] Falha ao enviar mensagem: {e}")
        return False


def load_id_file(path):
    """Lê um txt de IDs (um por linha), como os de 429 ou de idioma estrangeiro."""
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def append_id_file(path, new_ids):
    """Adiciona ao final do txt os IDs novos, sem duplicar os existentes."""
    known_ids = load_id_file(path)
    ids_to_add = [vid for vid in dict.fromkeys(new_ids) if vid not in known_ids]
    if not ids_to_add:
        return 0

    needs_newline = False
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            needs_newline = f.read(1) != b"\n"

    with open(path, "a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        f.write("\n".join(ids_to_add) + "\n")
    return len(ids_to_add)


def load_and_filter_csv(csv_path, synced_ids: set[str], skip_ids=frozenset()):
    """Lê o CSV original e remove os IDs já sincronizados no Postgres ou na lista de exclusão."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Arquivo CSV nao encontrado em: {csv_path}")

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    pending_rows = []
    already_processed = 0
    skipped_429 = 0

    for row in rows:
        vid = row.get("Video_id") or row.get("video_id")
        if vid and str(vid).strip() in synced_ids:
            already_processed += 1
        elif vid and str(vid).strip() in skip_ids:
            skipped_429 += 1
        else:
            pending_rows.append(row)

    original_total = len(rows)
    print(
        f"[INIT] Total CSV: {original_total} | Ja sincronizados no DB:"
        f" {already_processed} | Pulados (lista de exclusao): {skipped_429} |"
        f" Pendentes: {len(pending_rows)}"
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
        # '=' evita que o argparse trate IDs iniciados por '-' como uma flag
        f"--id={video_id}",
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
    Gera a string padronizada para a coluna file_format
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
    profile_id: int,
    video_id: str,
    abs_output_dir: str,
    download_opts: dict,
) -> None:
    """
    1. Envia dados brutos do vídeo para o bucket S3.
    2. Registra metadados consolidados na tabela phd_pipeline.transcript no Postgres.
    3. Exclui a pasta local de dados brutos do vídeo.
    """
    video_folder = os.path.join(abs_output_dir, str(video_id))
    if not os.path.exists(video_folder):
        return

    # Etapa 1: Upload para o bucket S3
    uploaded_assets = sync_manager.upload_video_assets_to_s3(
        youtube_video_id=str(video_id),
        video_folder=video_folder,
    )

    if not uploaded_assets:
        shutil.rmtree(video_folder, ignore_errors=True)
        return

    print(
        f">> [PERFIL {profile_id}] [{video_id}] [S3] Upload concluido"
        f" ({len(uploaded_assets)} arquivo(s)).",
        flush=True,
    )

    modality_str = resolve_downloaded_modality_label(download_opts)
    total_size_bytes = sum(a["size_bytes"] for a in uploaded_assets)
    bucket_prefix_key = f"data/{video_id}"

    has_manual_sub = any(
        a["filename"].lower().startswith("manual_")
        and a["filename"].lower().endswith((".srt", ".vtt"))
        for a in uploaded_assets
    )
    source_type = "YOUTUBE_MANUAL" if has_manual_sub else "YOUTUBE_AUTOMATIC"

    # Etapa 2: Registro único consolidado no Postgres
    record = TranscriptRecord(
        youtube_video_id=str(video_id),
        source_type=source_type,
        language_code="pt",
        file_format=modality_str,
        s3_bucket=uploaded_assets[0]["s3_bucket"],
        bucket_key=bucket_prefix_key,
        size_bytes=total_size_bytes,
    )
    sync_manager.save_transcript_to_db(record)

    print(
        f">> [PERFIL {profile_id}] [{video_id}] [POSTGRES] Metadados salvos"
        f" ({modality_str} | {bucket_prefix_key}).",
        flush=True,
    )

    # Etapa 3: Exclusão dos dados brutos locais
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

    # formata as tags ativas para o log (ex: [audio,subs])
    short_tags = []
    if download_opts.get("audio"):
        short_tags.append("audio")
    if download_opts.get("subtitles"):
        short_tags.append("subs")
    if download_opts.get("frames"):
        short_tags.append("frames")
    if download_opts.get("thumbnail"):
        short_tags.append("thumb")
    tags_label = f"[{','.join(short_tags)}]"

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
        session_blocked = False
        rate_limited_ids = []
        foreign_ids = []
        cookie_name = os.path.basename(cookie_path)
        abs_output_dir = os.path.abspath(output_dir)

        for idx, row in enumerate(rows, start=1):
            time.sleep(random.uniform(2, 6))  # pequena pausa para não dar merda
            video_id = row.get("Video_id") or row.get("video_id")
            if not video_id:
                continue

            print(
                f"[PERFIL {profile_id}] iniciando processamento {video_id} {tags_label}",
                flush=True,
            )

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

            # Filtra apenas eventos relevantes de rede/bloqueio emitidos pelo downloader
            for line in combined_output.splitlines():
                clean_line = line.strip()
                if any(
                    tag in clean_line.lower()
                    for tag in (
                        "bloqueio/rate-limit detectado",
                        "rate-limit de sessao",
                        "roteando trafego",
                        "falha critica",
                        "erro no processamento",
                    )
                ):
                    print(
                        f">> [PERFIL {profile_id}] [{video_id}] {clean_line}",
                        flush=True,
                    )

            if proc.returncode == 0:
                print(
                    f">> [PERFIL {profile_id}] [{video_id}] ({idx}/{len(rows)})"
                    " [DOWNLOAD] Concluido.",
                    flush=True,
                )
                try:
                    persist_and_cleanup_video(
                        sync_manager=sync_manager,
                        profile_id=profile_id,
                        video_id=video_id,
                        abs_output_dir=abs_output_dir,
                        download_opts=download_opts,
                    )
                    extracted_videos += 1
                    if row in pending_videos:
                        pending_videos.remove(row)
                except Exception as sync_err:
                    print(
                        f">> [PERFIL {profile_id}] [{video_id}] [ERRO][SYNC] Falha"
                        f" ao salvar no S3/DB: {sync_err}",
                        flush=True,
                    )
            elif proc.returncode == 2:
                print(
                    f">> [PERFIL {profile_id}] [{video_id}] [PULADO] Video indisponivel ou privado.",
                    flush=True,
                )
                if row in pending_videos:
                    pending_videos.remove(row)
                continue
            elif proc.returncode == 4:
                print(
                    f">> [PERFIL {profile_id}] [{video_id}] [PULADO] Video com restricao de idade.",
                    flush=True,
                )
                if row in pending_videos:
                    pending_videos.remove(row)
                continue
            elif proc.returncode == 6:
                print(
                    f">> [PERFIL {profile_id}] [{video_id}] [PULADO] Video fora do idioma pt.",
                    flush=True,
                )
                foreign_ids.append(str(video_id).strip())
                if row in pending_videos:
                    pending_videos.remove(row)
                continue
            elif proc.returncode == 5:
                print(
                    f">> [PERFIL {profile_id}] [{video_id}] [PULADO] Erro 429, ID sera registrado no txt de 429.",
                    flush=True,
                )
                rate_limited_ids.append(str(video_id).strip())
                if row in pending_videos:
                    pending_videos.remove(row)
                continue
            elif proc.returncode == 3:
                session_blocked = True
                print(
                    f">> [PERFIL {profile_id}] [{video_id}] [COOKIE BLOQUEADO]"
                    f" Rate-limit de sessao do YouTube (cookie '{cookie_name}')."
                    " Worker encerrado.",
                    flush=True,
                )
                session_msg = (
                    f"*Cookie com Rate-limit de Sessao (Perfil {profile_id})*\n"
                    f"- Cookie: `{cookie_name}`\n"
                    f"- Video: `{video_id}`\n"
                    "- Causa: sessao limitada pelo YouTube (ate ~1h); nao e"
                    " bloqueio de IP.\n"
                    "- Acao: Worker encerrado preventivamente."
                )
                send_telegram_message(session_msg, bot_token, chat_id)
                break
            else:
                if (
                    "bloqueio/rate-limit detectado" in combined_output.lower()
                    or "falha critica" in combined_output.lower()
                ):
                    block_detected = True
                    block_msg = (
                        f"*Bloqueio Detectado (Perfil {profile_id})*\n"
                        f"- Cookie: `{cookie_name}`\n"
                        f"- Video: `{video_id}`\n"
                        "- Acao: Worker encerrado preventivamente."
                    )
                    send_telegram_message(block_msg, bot_token, chat_id)
                    break

        total_time = time.time() - start_time
        formatted_time = str(timedelta(seconds=int(total_time)))

        os.makedirs("relatorios", exist_ok=True)
        report_path = os.path.join(
            "relatorios", f"relatorio_perfil_{profile_id}.txt"
        )

        if session_blocked:
            status_label = "BLOQUEADO (Cookie/Sessao)"
        elif block_detected:
            status_label = "BLOQUEADO (Bot Block)"
        else:
            status_label = "CONCLUIDO"

        report_content = (
            f"========================================\n"
            f"RELATORIO DE EXTRACAO - PERFIL {profile_id}\n"
            f"========================================\n"
            f"Arquivo de Cookie: {cookie_name}\n"
            f"Total de Videos Alocados: {len(rows)}\n"
            f"Videos Extraidos e Sincronizados: {extracted_videos}\n"
            f"Videos Pendentes/Restantes: {len(pending_videos)}\n"
            f"Videos com erro 429: {len(rate_limited_ids)}\n"
            f"Videos fora do idioma pt: {len(foreign_ids)}\n"
            f"Status Final: {status_label}\n"
            f"Tempo de Execucao: {formatted_time}\n"
            f"========================================\n"
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        telegram_msg = (
            f"*Relatorio do Perfil {profile_id}*\n\n"
            f"*Cookie:* `{cookie_name}`\n"
            f"*Sincronizados (S3 + DB):* {extracted_videos}/{len(rows)}\n"
            f"*Pendentes:* {len(pending_videos)}\n"
            f"*Tempo:* {formatted_time}\n"
            f"*Status:* {status_label}"
        )
        send_telegram_message(telegram_msg, bot_token, chat_id)

        return {
            "profile_id": profile_id,
            "extracted": extracted_videos,
            "pending": pending_videos,
            "rate_limited": rate_limited_ids,
            "foreign": foreign_ids,
            "blocked": block_detected or session_blocked,
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
        print(
            f"[ERRO] Nenhum arquivo de cookie .txt encontrado em '{cookies_dir}'."
        )
        sys.exit(1)

    print(f"[INIT] Cookies encontrados: {len(cookie_files)}")
    print(f"[INIT] Modulos ativos: {', '.join(active_modules)}")
    if use_proxies and raw_proxies:
        print(f"[INIT] Rotacao de proxies ativa: {raw_proxies}")

    root_sync = StorageSyncManager(pg_config=pg_config, s3_config=s3_config)
    synced_ids = root_sync.get_already_synced_youtube_ids()

    ids_429_path = config.get("DEFAULT", "ids_429", fallback="ids_429.txt")
    known_429_ids = load_id_file(ids_429_path)
    print(f"[INIT] IDs com 429 conhecidos em '{ids_429_path}': {len(known_429_ids)}")

    ids_foreign_path = config.get("DEFAULT", "ids_foreign", fallback="ids_foreign.txt")
    known_foreign_ids = load_id_file(ids_foreign_path)
    print(
        f"[INIT] IDs fora do idioma pt conhecidos em '{ids_foreign_path}':"
        f" {len(known_foreign_ids)}"
    )

    (
        filtered_csv_path,
        pending_records,
        headers,
        original_total,
        already_processed,
    ) = load_and_filter_csv(
        target_csv, synced_ids, known_429_ids | known_foreign_ids
    )

    if not pending_records:
        print("[INIT] Todos os videos do CSV ja estao sincronizados. Encerrando.")
        send_telegram_message(
            "*Aviso:* Todos os videos do CSV informado ja foram processados e"
            " sincronizados anteriormente.",
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
        f"*INICIANDO NOVO CICLO DE EXTRACAO*\n\n"
        f"*Modulos Ativos:* `{', '.join(active_modules)}`\n"
        f"*Rede/Proxies:* `{proxy_status_str}`\n"
        f"*Total no CSV Alvo:* {original_total}\n"
        f"*Ja Sincronizados no DB:* {already_processed}\n"
        f"*Faltam Processar:* {len(pending_records)}\n"
        f"*Perfis/Cookies Ativos:* {num_cookies}\n"
        f"*Media por Perfil:* ~{slice_size} videos\n\n"
        "_Fluxo ativo: Download -> S3 -> Postgres -> Limpeza local por video._"
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
                print(f"[ERRO][WORKER] Falha na execucao do perfil: {e}")

    all_unextracted = []
    new_429_ids = []
    new_foreign_ids = []
    total_extracted = 0
    total_blocks = 0

    for res in results:
        total_extracted += res["extracted"]
        all_unextracted.extend(res["pending"])
        new_429_ids.extend(res["rate_limited"])
        new_foreign_ids.extend(res["foreign"])
        if res["blocked"]:
            total_blocks += 1

    added_429 = append_id_file(ids_429_path, new_429_ids)
    print(f"[429] {added_429} novo(s) ID(s) adicionado(s) a '{ids_429_path}'.")
    added_foreign = append_id_file(ids_foreign_path, new_foreign_ids)
    print(
        f"[IDIOMA] {added_foreign} novo(s) ID(s) adicionado(s) a"
        f" '{ids_foreign_path}'."
    )

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
        f"RESUMO DE EXECUCAO PARALELA\n"
        f"========================================\n"
        f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Modulos extraidos: {', '.join(active_modules)}\n"
        f"Perfis de cookies utilizados: {num_cookies}\n"
        f"Total de videos sincronizados nesta sessao: {total_extracted}\n"
        f"Total de videos que ainda faltam: {len(all_unextracted)}\n"
        f"Novos IDs com erro 429 registrados: {added_429}\n"
        f"Novos IDs fora do idioma pt registrados: {added_foreign}\n"
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
        f"*EXECUCAO PARALELA FINALIZADA*\n\n"
        f"*Modulos:* `{', '.join(active_modules)}`\n"
        f"*Total Sincronizados Nesta Sessao:* {total_extracted}\n"
        f"*Ainda Pendentes:* {len(all_unextracted)}\n"
        f"*Contas Bloqueadas:* {total_blocks}/{num_cookies}\n"
        f"*Tempo Total:* {overall_total_time}\n\n"
        "Os relatorios individuais e o resumo geral foram salvos na pasta"
        f" `{final_reports_dir}/`.\n"
        f"O CSV final com as pendencias foi atualizado em `{final_pending_csv}`."
    )
    send_telegram_message(final_msg, bot_token, chat_id)
    print("\n[FIM] Execucao e consolidacao final concluidas com sucesso.")


if __name__ == "__main__":
    main()
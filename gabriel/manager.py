import os
import sys
import csv
import math
import time
import glob
import shutil
import requests
import argparse
import configparser
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, as_completed

def load_configuration(conf_path):
    """Lê e valida o arquivo de configuração .conf."""
    if not os.path.exists(conf_path):
        print(f"Error: Configuration file '{conf_path}' not found.")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(conf_path, encoding='utf-8')
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

def validate_video_already_extracted(video_id, output_dir):
    """Verifica se o vídeo já foi extraído com sucesso (pasta 'frames' não vazia)."""
    frames_dir = os.path.join(output_dir, str(video_id), "frames")
    if os.path.exists(frames_dir):
        files = [f for f in os.listdir(frames_dir) if not f.startswith('.')]
        if len(files) > 0:
            return True
    return False

def load_and_filter_csv(csv_path, output_dir):
    """Lê o CSV original e remove os IDs que já possuem extração concluída."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found at: {csv_path}")

    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    pending_rows = []
    already_processed = 0

    for row in rows:
        vid = row.get('Video_id') or row.get('video_id')
        if vid and validate_video_already_extracted(vid, output_dir):
            already_processed += 1
        else:
            pending_rows.append(row)

    original_total = len(rows)
    print(f"[Step 1] Original total: {original_total} | Already processed: {already_processed} | Pending: {len(pending_rows)}")

    pending_csv_path = "csv_pending_execution.csv"
    with open(pending_csv_path, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pending_rows)

    return pending_csv_path, pending_rows, fieldnames, original_total, already_processed

def worker_process(profile_id, csv_slice, cookie_path, output_dir, extract_subs, bot_token, chat_id, use_proxies, proxy_list):
    """Executado isoladamente em paralelo para cada cookie."""
    start_time = time.time()
    work_dir = f"worker_env_profile_{profile_id}"
    os.makedirs(work_dir, exist_ok=True)

    shutil.copy(cookie_path, os.path.join(work_dir, "cookies_base.txt"))
    shutil.copy("video_downloader.py", os.path.join(work_dir, "video_downloader.py"))
    
    local_csv = os.path.join(work_dir, f"sub_target_{profile_id}.csv")
    
    with open(csv_slice["path"], 'r', encoding='utf-8') as sf, open(local_csv, 'w', encoding='utf-8') as tf:
        tf.write(sf.read())

    original_cwd = os.getcwd()
    os.chdir(work_dir)
    sys.path.insert(0, os.getcwd())

    import video_downloader

    with open(f"sub_target_{profile_id}.csv", mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)

    pending_videos = rows.copy()
    extracted_videos = 0
    block_detected = False

    abs_output_dir = os.path.abspath(os.path.join("..", output_dir))

    for row in rows:
        video_id = row.get('Video_id') or row.get('video_id')
        if video_id:
            status = video_downloader.process_video(
                video_id, 
                extract_subs, 
                abs_output_dir, 
                bot_token, 
                chat_id, 
                use_proxies, 
                proxy_list
            )
            
            if status == "BOT_BLOCK":
                block_detected = True
                break
            elif status == "SUCCESS":
                extracted_videos += 1
                if row in pending_videos:
                    pending_videos.remove(row)

    with open(f"sub_target_{profile_id}.csv", mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(pending_videos)

    os.chdir(original_cwd)

    total_time = time.time() - start_time
    formatted_time = str(timedelta(seconds=int(total_time)))
    cookie_name = os.path.basename(cookie_path)

    os.makedirs("relatorios", exist_ok=True)
    report_path = os.path.join("relatorios", f"relatorio_perfil_{profile_id}.txt")
    
    # Mantendo o relatório em português conforme solicitado
    report_content = (
        f"========================================\n"
        f"RELATÓRIO DE EXTRAÇÃO - PERFIL {profile_id}\n"
        f"========================================\n"
        f"Arquivo de Cookie: {cookie_name}\n"
        f"Total de Vídeos Alocados: {len(rows)}\n"
        f"Vídeos Extraídos com Sucesso: {extracted_videos}\n"
        f"Vídeos Pendentes/Restantes: {len(pending_videos)}\n"
        f"Status Final: {'BLOQUEADO (Bot Block)' if block_detected else 'CONCLUÍDO'}\n"
        f"Tempo de Execução: {formatted_time}\n"
        f"========================================\n"
    )

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    # Mantendo a mensagem do Telegram em português
    telegram_msg = (
        f"📊 *Relatório do Perfil {profile_id}*\n\n"
        f"• *Cookie:* `{cookie_name}`\n"
        f"• *Extraídos:* {extracted_videos}/{len(rows)}\n"
        f"• *Pendentes:* {len(pending_videos)}\n"
        f"• *Tempo:* {formatted_time}\n"
        f"• *Status:* {' Bloqueado pelo YouTube' if block_detected else ' Finalizado com Sucesso'}"
    )
    send_telegram_message(telegram_msg, bot_token, chat_id)

    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    return {
        "profile_id": profile_id,
        "extracted": extracted_videos,
        "pending": pending_videos,
        "blocked": block_detected,
        "time": total_time,
        "fieldnames": headers
    }

def main():
    parser = argparse.ArgumentParser(description="Parallel Extractor Orchestrator with .conf file")
    parser.add_argument("--conf", type=str, default="config.conf", help="Path to .conf configuration file")
    args = parser.parse_args()

    config = load_configuration(args.conf)

    # Lendo variáveis da seção DEFAULT
    cookies_dir = config.get("DEFAULT", "cookies_dir", fallback="cookies")
    output_dir = config.get("DEFAULT", "output_dir", fallback="output")
    target_csv = config.get("DEFAULT", "csv_alvo", fallback="lista_alvos.csv")
    extract_subs = config.getboolean("DEFAULT", "extrair_subs", fallback=False)
    
    # Lendo configurações de proxies
    use_proxies = config.getboolean("DEFAULT", "using_proxy", fallback=False)
    raw_proxies = config.get("DEFAULT", "proxies_list", fallback="")
    proxy_list = [p.strip() for p in raw_proxies.split(",")] if raw_proxies else []

    # Lendo variáveis da seção TELEGRAM
    bot_token = config.get("TELEGRAM", "bot_token", fallback="")
    chat_id = config.get("TELEGRAM", "chat_id", fallback="")

    global_start = time.time()

    cookie_files = sorted(glob.glob(os.path.join(cookies_dir, "*.txt")))
    if not cookie_files:
        print(f"Error: No .txt cookie file found in '{cookies_dir}'.")
        sys.exit(1)

    print(f"Found {len(cookie_files)} cookies for processing.")

    # Passo 1: Filtrar CSV
    filtered_csv_path, pending_records, headers, original_total, already_processed = load_and_filter_csv(target_csv, output_dir)

    if not pending_records:
        print("All videos from the CSV have already been extracted. Exiting.")
        send_telegram_message("ℹ️ *Aviso:* Todos os vídeos do CSV informado já foram processados anteriormente.", bot_token, chat_id)
        sys.exit(0)

    num_cookies = len(cookie_files)
    slice_size = math.ceil(len(pending_records) / num_cookies)
    slices = [pending_records[i:i + slice_size] for i in range(0, len(pending_records), slice_size)]

    sub_csv_files = []
    os.makedirs("sub_csvs", exist_ok=True)
    
    for idx, current_slice in enumerate(slices):
        sub_path = os.path.join("sub_csvs", f"sub_{idx + 1}.csv")
        with open(sub_path, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(current_slice)
        sub_csv_files.append({"path": sub_path, "quantity": len(current_slice)})

    # Mantendo a mensagem do Telegram em português
    start_msg = (
        f" *INICIANDO NOVO CICLO DE EXTRAÇÃO*\n\n"
        f"• *Total no CSV Alvo:* {original_total}\n"
        f"• *Já Extraídos Anteriormente:* {already_processed}\n"
        f"• *Faltam Processar:* {len(pending_records)}\n"
        f"• *Perfis/Cookies Ativos:* {num_cookies}\n"
        f"• *Média por Perfil:* ~{slice_size} vídeos\n\n"
        f" _Os downloads foram disparados em paralelo e relatórios parciais serão enviados conforme a conclusão de cada perfil._"
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
                    extract_subs,
                    bot_token,
                    chat_id,
                    use_proxies,
                    proxy_list
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
    with open(final_pending_csv, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(all_unextracted)

    final_reports_dir = "relatorios_consolidados"
    os.makedirs(final_reports_dir, exist_ok=True)
    
    for report_file in glob.glob("relatorios/relatorio_perfil_*.txt"):
        shutil.move(report_file, os.path.join(final_reports_dir, os.path.basename(report_file)))

    overall_total_time = str(timedelta(seconds=int(time.time() - global_start)))

    # Mantendo o relatório em português
    general_report_path = os.path.join(final_reports_dir, "RESUMO_GERAL_EXECUCAO.txt")
    summary_text = (
        f"========================================\n"
        f"RESUMO DE EXECUÇÃO PARALELA MULTI-COOKIES\n"
        f"========================================\n"
        f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Perfis de cookies utilizados: {num_cookies}\n"
        f"Total de vídeos baixados nesta sessão: {total_extracted}\n"
        f"Total de vídeos que ainda faltam: {len(all_unextracted)}\n"
        f"Contas/Cookies que sofreram bloqueio: {total_blocks}\n"
        f"Tempo total decorrido: {overall_total_time}\n"
        f"========================================\n"
    )
    with open(general_report_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)

    shutil.rmtree("sub_csvs", ignore_errors=True)
    if os.path.exists("relatorios"):
        shutil.rmtree("relatorios", ignore_errors=True)
    if os.path.exists(filtered_csv_path):
        os.remove(filtered_csv_path)

    # Mantendo a mensagem do Telegram em português
    final_msg = (
        f" *EXECUÇÃO PARALELA FINALIZADA*\n\n"
        f"• *Total Baixados Nesta Sessão:* {total_extracted}\n"
        f"• *Ainda Pendentes:* {len(all_unextracted)}\n"
        f"• *Contas Bloqueadas:* {total_blocks}/{num_cookies}\n"
        f"• *Tempo Total:* {overall_total_time}\n\n"
        f" Os relatórios individuais e o resumo geral foram salvos na pasta `{final_reports_dir}/`.\n"
        f" O CSV final com as pendências foi atualizado em `{final_pending_csv}`."
    )
    send_telegram_message(final_msg, bot_token, chat_id)
    print("\nExecution and final consolidation completed successfully!")

if __name__ == "__main__":
    main()
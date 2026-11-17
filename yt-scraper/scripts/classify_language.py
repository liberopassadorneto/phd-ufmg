import argparse
import csv
from collections import Counter
import os
import random
import time

import yt_dlp


class _SilentLogger:
    """Suprime mensagens de debug, avisos e erros do yt-dlp."""

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def classify(info):
    """
    Classifica o vídeo pelos metadados: 'language' e a legenda automática
    original em português ('pt-orig').
    """
    language = (info.get("language") or "").lower()
    has_pt_orig = "pt-orig" in (info.get("automatic_captions") or {})

    is_portuguese = language.startswith("pt") or has_pt_orig
    is_foreign = bool(language) and not language.startswith("pt")

    if is_portuguese and is_foreign:
        return "CONFLITO", language, has_pt_orig
    if is_portuguese:
        return "PORTUGUES", language, has_pt_orig
    if is_foreign:
        return "ESTRANGEIRO", language, has_pt_orig
    return "INDEFINIDO", language, has_pt_orig


def fetch_info(video_id, proxy, cookies):
    """Extrai apenas os metadados do vídeo, sem baixar nada."""
    options = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "logger": _SilentLogger(),
    }
    if proxy:
        options["proxy"] = proxy
    if cookies:
        options["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False
        )


def load_done_ids(output_path):
    """IDs já classificados com sucesso (erros são refeitos na próxima rodada)."""
    if not os.path.exists(output_path):
        return set()
    with open(output_path, encoding="utf-8", newline="") as f:
        return {
            row["video_id"] for row in csv.DictReader(f) if row["status"] != "ERRO"
        }


def main():
    parser = argparse.ArgumentParser(
        description="Classifica IDs do YouTube como português ou estrangeiro"
    )
    parser.add_argument("ids_file", help="TXT com um ID por linha")
    parser.add_argument("--output", default="languages.csv", help="CSV de saída")
    parser.add_argument("--proxy", default="", help="Ex.: socks5h://127.0.0.1:1080")
    parser.add_argument("--cookies", default="", help="Arquivo de cookies Netscape")
    parser.add_argument(
        "--delay", type=float, default=3.0, help="Pausa média entre vídeos (s)"
    )
    args = parser.parse_args()

    with open(args.ids_file, encoding="utf-8") as f:
        ids = list(dict.fromkeys(line.strip() for line in f if line.strip()))

    done_ids = load_done_ids(args.output)
    pending_ids = [vid for vid in ids if vid not in done_ids]
    print(f"[INIT] IDs: {len(ids)} | ja classificados: {len(done_ids)} | pendentes: {len(pending_ids)}")

    is_new_file = not os.path.exists(args.output)
    counter = Counter()

    with open(args.output, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if is_new_file:
            writer.writerow(["video_id", "status", "language", "has_pt_orig", "error"])

        for idx, video_id in enumerate(pending_ids, start=1):
            try:
                info = fetch_info(video_id, args.proxy, args.cookies)
                status, language, has_pt_orig = classify(info)
                writer.writerow([video_id, status, language, has_pt_orig, ""])
            except Exception as e:
                status = "ERRO"
                writer.writerow([video_id, status, "", "", repr(e)[:200]])

            f.flush()
            counter[status] += 1
            print(f"[{idx}/{len(pending_ids)}] {video_id}: {status}", flush=True)
            time.sleep(random.uniform(args.delay * 0.5, args.delay * 1.5))

    print("\n[FIM] Resumo desta rodada:")
    for status, total in counter.most_common():
        print(f"  {status}: {total}")


if __name__ == "__main__":
    main()
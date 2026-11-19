import argparse
import glob
import os
import re
import time

from playwright.sync_api import sync_playwright

WATCH_SECONDS = 5


def get_next_index(output_dir):
    """Retorna o próximo número livre para cookies-<num>.txt, sem sobrescrever."""
    numbers = [0]
    for path in glob.glob(os.path.join(output_dir, "cookies-*.txt")):
        match = re.search(r"cookies-(\d+)\.txt$", path)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers) + 1


def to_netscape(cookies):
    """Converte a lista de cookies do Playwright para o formato Netscape."""
    lines = ["# Netscape HTTP Cookie File", ""]
    for cookie in cookies:
        domain = cookie["domain"]
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        if cookie.get("httpOnly"):
            domain = f"#HttpOnly_{domain}"
        secure = "TRUE" if cookie.get("secure") else "FALSE"
        # cookies de sessão (expires = -1) são gravados com expiração 0
        expires = int(cookie["expires"]) if cookie.get("expires", -1) > 0 else 0
        lines.append(
            "\t".join(
                [
                    domain,
                    include_subdomains,
                    cookie["path"],
                    secure,
                    str(expires),
                    cookie["name"],
                    cookie["value"],
                ]
            )
        )
    return "\n".join(lines) + "\n"


def generate_cookie(browser, query, proxy, output_path):
    """Abre uma sessão limpa, pesquisa e abre um vídeo, e salva os cookies."""
    context = browser.new_context(
        locale="pt-BR",
        proxy={"server": proxy} if proxy else None,
        bypass_csp=True,
    )
    try:
        page = context.new_page()
        page.goto("https://www.youtube.com", wait_until="domcontentloaded")
        page.fill("input[name='search_query']", query)
        page.keyboard.press("Enter")
        # confirma que a pesquisa foi enviada e os resultados carregaram
        page.wait_for_url(re.compile(r"/results\?search_query="))

        # primeiro vídeo visível da lista (shorts usam /shorts/, então ficam de fora)
        first_video = page.locator("a[href^='/watch?v=']:visible").first
        first_video.wait_for(state="visible")
        first_video.click()

        # confirma que a página do vídeo abriu e que ele começou a tocar
        page.wait_for_url(re.compile(r"/watch\?v="))
        page.wait_for_function(
            "document.querySelector('video') &&"
            " document.querySelector('video').currentTime > 0",
            timeout=30000,
        )
        # tempo para o YouTube definir os cookies de visitante
        time.sleep(WATCH_SECONDS)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(to_netscape(context.cookies()))
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description="Gerador de cookies do YouTube")
    parser.add_argument("count", type=int, help="Quantidade de cookies a gerar")
    parser.add_argument(
        "--output", type=str, default="cookies", help="Pasta de saída"
    )
    parser.add_argument(
        "--query", type=str, default="música", help="Termo pesquisado no YouTube"
    )
    parser.add_argument(
        "--proxy",
        type=str,
        default="",
        help="Proxy do navegador (ex.: socks5://127.0.0.1:1080)",
    )
    parser.add_argument(
        "--headless", action="store_true", help="Executa sem abrir a janela"
    )
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    # o Chromium não aceita socks5h://, mas já resolve o DNS pelo proxy
    proxy = args.proxy.replace("socks5h://", "socks5://")
    start_index = get_next_index(args.output)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=args.headless, args=["--mute-audio"]
        )
        for i in range(args.count):
            output_path = os.path.join(
                args.output, f"cookies-{start_index + i}.txt"
            )
            try:
                generate_cookie(browser, args.query, proxy, output_path)
                print(f"[OK] {output_path}")
            except Exception as e:
                print(f"[ERRO] {output_path}: {e!r}")
        browser.close()


if __name__ == "__main__":
    main()
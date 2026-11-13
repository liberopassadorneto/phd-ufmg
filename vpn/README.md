# Guia Rápido: Acesso SSH e Túneis via Tailscale (Docker / Userspace)

Como o Tailscale roda em modo *userspace* dentro de um container Docker (sem modificar as rotas do kernel do servidor host), todo tráfego de saída para a rede `100.x.y.z` precisa atravessar o proxy SOCKS5 exposto pelo container na porta `127.0.0.1:1055`.

---

## 1. Pré-requisito no Servidor Local

Certifique-se de que o container do Tailscale está rodando com o proxy SOCKS5 ativo na porta `1055` e que o pacote `netcat` (`nc`) com suporte a SOCKS5 está instalado:

```bash
# Verifica se o container está ouvindo na porta 1055
ss -tulpn | grep 1055

# Testa se o netcat suporta a flag -X (OpenBSD netcat)
nc -h 2>&1 | grep -- "-X"

```

*(Se o `nc` não suportar `-X`, instale o `netcat-openbsd` ou use `connect-proxy` / `socat`).*

---

## 2. Acesso SSH Direto via Proxy SOCKS5 (Porta 1055)

Para abrir um terminal remoto em outro servidor da rede Tailscale passando pelo túnel do container:

```bash
ssh -o ProxyCommand="nc -X 5 -x 127.0.0.1:1055 %h %p" usuario@100.x.y.z

```

### O que cada parâmetro faz:

* `ProxyCommand="nc -X 5 -x 127.0.0.1:1055 %h %p"`: Instrui o SSH a encapsular a conexão dentro do proxy SOCKS5 (`-X 5`) rodando em `127.0.0.1:1055`, substituindo `%h` pelo IP da VPN e `%p` pela porta SSH.
* `100.x.y.z`: IP virtual da máquina de destino na sua tailnet.

---

## 3. Simplificando com `~/.ssh/config` (Recomendado)

Para não precisar digitar o `ProxyCommand` toda vez, configure uma regra automática no arquivo `~/.ssh/config` para qualquer IP da faixa do Tailscale (`100.*`):

```text
Host 100.*
    ProxyCommand nc -X 5 -x 127.0.0.1:1055 %h %p
    ServerAliveInterval 60

# Atalhos nomeados opcionais:
Host servidor-2
    HostName 100.x.y.z
    User usuario

```

Com isso configurado, os comandos ficam limpos:

```bash
ssh usuario@100.x.y.z
# ou usando o apelido:
ssh servidor-2

```

---

## 4. Criando Túneis SSH sobre o Tailscale

Mesmo passando pelo proxy SOCKS5 da porta `1055`, você pode encadear túneis SSH normalmente para encaminhar portas de serviços internos (como PostgreSQL, APIs ou painéis web).

### A) Encaminhamento de Porta Local (`-L`)

Trazer uma porta do servidor remoto (`100.x.y.z`) para o `localhost` desta máquina:

```bash
ssh -f -N \
  -o ProxyCommand="nc -X 5 -x 127.0.0.1:1055 %h %p" \
  -L 5433:127.0.0.1:5433 \
  usuario@100.x.y.z

```

* Se você já configurou o `~/.ssh/config` (Passo 3), basta rodar:
```bash
ssh -f -N -L 5433:127.0.0.1:5433 servidor-2

```


* **Uso:** Conecte sua aplicação ou script diretamente em `127.0.0.1:5433`.

### B) Túnel Dinâmico Secundário (`-D 1080`)

Caso queira abrir um segundo proxy SOCKS5 na porta `1080` saindo especificamente pelo IP da **Máquina 2** (útil para navegar ou fazer requisições usando o IP externo da Máquina 2):

```bash
ssh -f -N \
  -o ProxyCommand="nc -X 5 -x 127.0.0.1:1055 %h %p" \
  -D 1080 \
  usuario@100.x.y.z

```

---

## 5. Outros Comandos Úteis pela VPN (Sem SSH)

Como o container já expõe o proxy SOCKS5 e HTTP na porta `1055`, ferramentas que não usam SSH podem falar direto com os outros nós da tailnet:

* **Transferir arquivos via SCP / Rsync:**
```bash
scp -o ProxyCommand="nc -X 5 -x 127.0.0.1:1055 %h %p" arquivo.sql usuario@100.x.y.z:/tmp/

```


* **Requisições HTTP/API com cURL:**
```bash
curl --socks5-hostname 127.0.0.1:1055 [http://100.](http://100.)x.y.z:8000/health

```


* **Scripts Python / Terminal inteiro:**
```bash
export ALL_PROXY=socks5h://127.0.0.1:1055

```



---

## 6. Gerenciar e Encerrar Túneis Ativos

* **Listar túneis em segundo plano:**
```bash
ps aux | grep "ssh -f -N"

```


* **Encerrar todos os túneis abertos:**
```bash
pkill -f "ssh -f -N"

```
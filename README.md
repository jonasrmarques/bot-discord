# Bot Discord — Aniversários com IA (Groq)

Bot em Python que agenda parabéns diários às **09:00** (fuso configurável), gera texto com a **Groq** e envia no canal definido por `CHANNEL_ID`. Aniversários ficam em `birthdays.json`; o arquivo `birthday_state.json` (criado automaticamente) evita **reenviar no mesmo dia** se o processo reiniciar após o envio.

## Requisitos

- Python **3.10+**
- Conta [Discord Developer Portal](https://discord.com/developers/applications) (bot + token)
- Chave [Groq Console](https://console.groq.com/) (`GROQ_API_KEY`)

### Intents no Discord

No portal, em **Bot** → **Privileged Gateway Intents**, ative:

- **MESSAGE CONTENT INTENT** (obrigatório para comandos com `!`)
- **SERVER MEMBERS INTENT** (recomendado para nomes de exibição no servidor)

Convide o bot com permissões de **Ler mensagens**, **Enviar mensagens** e **Mencionar** no canal de aniversários.

## Instalação local

```bash
python -m venv .venv
```

**Windows (PowerShell):**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha:

- `DISCORD_TOKEN` — token do bot
- `GROQ_API_KEY` — chave da API Groq
- `CHANNEL_ID` — ID numérico do canal de texto (modo desenvolvedor no Discord → copiar ID)
- `TIMEZONE` — opcional, fuso [IANA](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (padrão `America/Sao_Paulo`)
- `GROQ_MODEL` — opcional (padrão `llama3-70b-8192`)

## Como rodar

Na raiz do projeto:

```bash
python main.py
```

Com o bot online, no servidor:

- `!addbirthday Nome DD-MM` — exemplo: `!addbirthday Rogério 29-01` (só texto, sem @)
- `!listbirthdays` — lista todos (chaves no JSON em **MM-DD**)
- `!helpbirthday` — resumo

## Formato do `birthdays.json`

O comando usa **DD-MM**; no arquivo a chave é **MM-DD** e cada lista guarda **nomes** (texto), por exemplo:

```json
{
  "04-02": ["Rogério"]
}
```

O envio automático **não usa menção @** no Discord; o nome aparece em negrito na mensagem.

## Deploy (ex.: Render)

1. Suba o repositório para o GitHub (ou Git conectado ao Render).
2. Crie um **Background Worker** (recomendado: não precisa de HTTP) ou um **Web Service** com comando que só mantém o processo vivo.
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python main.py`
5. Em **Environment**, defina `DISCORD_TOKEN`, `GROQ_API_KEY`, `CHANNEL_ID` e, se quiser, `TIMEZONE`.

**Persistência:** em disco efêmero (plano free), `birthdays.json` e `birthday_state.json` podem ser perdidos ao redeploy. Para produção, use volume persistente ou migre o armazenamento para banco (ex.: SQLite em volume).

## Estrutura

| Arquivo / pasta        | Função                                      |
|------------------------|---------------------------------------------|
| `main.py`              | Bot, comandos, agendamento APScheduler      |
| `config.py`            | Leitura de variáveis de ambiente            |
| `birthdays.json`       | Mapa MM-DD → lista de IDs de usuário        |
| `services/ai_service.py`    | Chamada Groq (`gerar_mensagem`) e prompt |
| `services/birthday_service.py` | JSON, parsing DD-MM, anti-duplicata   |

## Licença

Use e adapte como quiser no seu servidor.

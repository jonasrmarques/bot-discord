"""
Ponto de entrada do bot Discord: comandos, agendamento diário (09:00) e envio com IA.

Requer intents no Developer Portal:
- MESSAGE CONTENT INTENT (comandos com prefixo !)
- SERVER MEMBERS INTENT (opcional, útil para display names em cache)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands
from dotenv import load_dotenv
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import load_config
from services import ai_service, birthday_service

if TYPE_CHECKING:
    from config import Config

# -----------------------------------------------------------------------------
# Logging básico no console (nível INFO + nome do logger)
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("birthday_bot")

ROOT = Path(__file__).resolve().parent
BIRTHDAY_IMAGE_PATH = ROOT / "static" / "image.png"

# Carrega .env local antes de ler config (não sobrescreve variáveis já definidas no SO)
load_dotenv()


def _make_bot(cfg: Config) -> commands.Bot:
    """Cria instância do bot com prefixo e intents necessários para comandos de texto."""
    intents = discord.Intents.default()
    intents.message_content = True  # Obrigatório para ler mensagens com prefixo
    intents.members = True  # Melhora cache de membros para display_name (ativar no Portal)

    return commands.Bot(command_prefix="!", intents=intents, help_command=None)


def _scheduler_for_timezone(tz_name: str) -> AsyncIOScheduler:
    """Inicializa o APScheduler com o fuso informado (ex.: America/Sao_Paulo)."""
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"TIMEZONE inválido: {tz_name}") from exc
    return AsyncIOScheduler(timezone=tz)


def _format_birthday_message(
    cfg: Config, nome: str, msg_text: str
) -> tuple[str, discord.AllowedMentions]:
    """Monta texto e permissões de menção conforme BIRTHDAY_MENTION."""
    body = f"**{nome}**\n{msg_text}"
    if cfg.birthday_mention == "everyone":
        return f"{body}\n@everyone", discord.AllowedMentions(everyone=True)
    if cfg.birthday_mention == "here":
        return f"{body}\n@here", discord.AllowedMentions(everyone=True)
    return body, discord.AllowedMentions.none()


def _birthday_image_file() -> discord.File | None:
    """Retorna anexo da imagem de aniversário, se existir no disco."""
    if not BIRTHDAY_IMAGE_PATH.is_file():
        logger.warning("Imagem %s não encontrada; enviando só texto.", BIRTHDAY_IMAGE_PATH)
        return None
    return discord.File(BIRTHDAY_IMAGE_PATH, filename="image.png")


async def send_daily_birthdays(bot: commands.Bot, cfg: Config) -> None:
    """
    Tarefa agendada: aniversariantes do dia (por nome no JSON), mensagem via Groq.
    Sem menção @: o nome aparece em destaque no texto. Usa birthday_state.json
    para não repetir no mesmo dia.
    """
    key = birthday_service.today_key(cfg.timezone)
    aniversariantes = birthday_service.get_birthdays_for_key(key)
    if not aniversariantes:
        logger.info("Nenhum aniversariante na data %s (chave MM-DD).", key)
        return

    channel = bot.get_channel(cfg.channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(cfg.channel_id)
        except discord.HTTPException as e:
            logger.error("Canal %s inacessível: %s", cfg.channel_id, e)
            return

    if not isinstance(channel, discord.TextChannel):
        logger.error("CHANNEL_ID deve apontar para um canal de texto.")
        return

    for person in aniversariantes:
        try:
            can_send, today_iso, _ = birthday_service.should_send_today(cfg.timezone, person.nome)
            if not can_send:
                logger.info(
                    "Já enviado hoje (%s) para %s; ignorando duplicata.", today_iso, person.nome
                )
                continue

            # gerar_mensagem trata erros da Groq e devolve fallback estável
            msg_text = ai_service.gerar_mensagem(person.nome, person.sexo)
            content, allowed = _format_birthday_message(cfg, person.nome, msg_text)
            image = _birthday_image_file()
            if image is not None:
                await channel.send(content, file=image, allowed_mentions=allowed)
            else:
                await channel.send(content, allowed_mentions=allowed)
            birthday_service.mark_sent(cfg.timezone, person.nome)
            logger.info(
                "Mensagem de aniversário enviada para %s no canal %s", person.nome, channel.id
            )

        except discord.HTTPException as e:
            logger.error("Erro Discord ao enviar para %s: %s", person.nome, e)
        except Exception:
            logger.exception("Erro inesperado ao processar aniversariante %s", person.nome)


def setup_commands(bot: commands.Bot, cfg: Config) -> None:
    """Registra comandos de prefixo (!addbirthday, !listbirthdays, !helpbirthday)."""

    @bot.command(name="addbirthday")
    async def add_birthday_cmd(ctx: commands.Context, *, texto: str) -> None:
        """
        Uso: !addbirthday Nome DD-MM [masculino|feminino]
        Salva nome e sexo no birthdays.json com chave MM-DD.
        """
        try:
            nome, date_fragment, sexo = birthday_service.parse_add_birthday_text(texto)
            key = birthday_service.add_birthday(nome, date_fragment, sexo)
        except ValueError as e:
            await ctx.send(f"❌ {e}")
            return
        await ctx.send(
            f"✅ Aniversário de **{nome}** ({sexo}) registrado para **{date_fragment}** "
            f"(chave `{key}` no JSON)."
        )

    @bot.command(name="listbirthdays")
    async def list_birthdays_cmd(ctx: commands.Context) -> None:
        """Lista todos os aniversários cadastrados (chave MM-DD e nomes)."""
        rows = birthday_service.list_birthdays_formatted()
        if not rows:
            await ctx.send("Nenhum aniversário cadastrado.")
            return
        lines: list[str] = []
        for mm_dd, people in rows:
            if not people:
                continue
            nomes_txt = ", ".join(f"{p.nome} ({p.sexo[0]})" for p in people)
            lines.append(f"**{mm_dd}** → {nomes_txt}")
        text = "\n".join(lines)
        if len(text) > 1900:
            text = text[:1900] + "\n… (lista truncada)"
        await ctx.send(text)

    @bot.command(name="helpbirthday")
    async def help_cmd(ctx: commands.Context) -> None:
        """Resumo dos comandos e variáveis de ambiente."""
        await ctx.send(
            "**Comandos**\n"
            "`!addbirthday Nome DD-MM [masculino|feminino]` — cadastra aniversário\n"
            "`!listbirthdays` — lista todos\n"
            f"**Agendamento:** todo dia às **09:00** ({cfg.timezone}) no canal <#{cfg.channel_id}>\n"
            "Variáveis: `DISCORD_TOKEN`, `GROQ_API_KEY`, `CHANNEL_ID`, opcional `TIMEZONE`, `GROQ_MODEL`, "
            "`BIRTHDAY_MENTION` (`everyone` | `here` | `off`), "
            "`RUN_BIRTHDAY_ON_START` (`1`/`once` ao subir; `force` = limpa estado do dia e roda)"
        )

    @add_birthday_cmd.error
    async def add_birthday_error(ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "Uso: `!addbirthday Nome DD-MM [masculino|feminino]` "
                "(ex.: `!addbirthday Rogério 29-01 masculino`)."
            )
        else:
            logger.exception("Erro em addbirthday: %s", error)
            await ctx.send("Ocorreu um erro ao processar o comando.")


def main() -> None:
    """Valida config, agenda job e inicia o loop do discord.py."""
    try:
        cfg = load_config()
    except ValueError as e:
        logger.error("%s", e)
        sys.exit(1)

    bot = _make_bot(cfg)
    setup_commands(bot, cfg)

    scheduler = _scheduler_for_timezone(cfg.timezone)
    # on_ready pode disparar de novo após reconexão; o job “ao subir” só uma vez por execução do processo
    _startup_birthday_ja_disparado = False

    @bot.event
    async def on_ready() -> None:
        nonlocal _startup_birthday_ja_disparado
        logger.info("Logado como %s (%s)", bot.user, bot.user.id if bot.user else "?")
        logger.info("Fuso para aniversários: %s — job diário às 09:00", cfg.timezone)
        logger.info("Menção em aniversários: %s", cfg.birthday_mention)
        if not scheduler.running:
            # Cron às 09:00 no fuso configurado (AsyncIOScheduler executa corrotinas no loop)
            scheduler.add_job(
                send_daily_birthdays,
                CronTrigger(hour=9, minute=0),
                args=[bot, cfg],
                id="daily_birthdays",
                replace_existing=True,
            )
            scheduler.start()

        # Teste local: RUN_BIRTHDAY_ON_START=1 roda o job ao subir; force zera estado do dia antes
        if cfg.run_birthday_on_start in ("once", "force") and not _startup_birthday_ja_disparado:
            _startup_birthday_ja_disparado = True
            if cfg.run_birthday_on_start == "force":
                birthday_service.reset_sent_for_today(cfg.timezone)
                logger.info("RUN_BIRTHDAY_ON_START=force — estado do dia limpo; disparando job agora.")
            asyncio.create_task(send_daily_birthdays(bot, cfg))
            logger.info("RUN_BIRTHDAY_ON_START: job de aniversários disparado na inicialização.")

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        if ctx.command is not None and ctx.command.name == "addbirthday":
            return  # já tratado no local error handler
        logger.warning("Erro de comando: %s", error)

    try:
        bot.run(cfg.discord_token)
    except discord.LoginFailure:
        logger.error("Token do Discord inválido.")
        sys.exit(1)


if __name__ == "__main__":
    main()

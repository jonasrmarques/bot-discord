"""
Carrega e valida configuração a partir de variáveis de ambiente.

Use um arquivo .env na raiz (opcional) com python-dotenv em main.py,
ou defina as variáveis no sistema / painel do hospedeiro (Render, etc.).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Config:
    """Configuração imutável do bot após leitura do ambiente."""

    discord_token: str
    channel_id: int
    timezone: str
    # off | once | force — ver RUN_BIRTHDAY_ON_START
    run_birthday_on_start: Literal["off", "once", "force"]
    # off | everyone | here — menção no envio automático de aniversário
    birthday_mention: Literal["off", "everyone", "here"]


def _parse_run_birthday_on_start() -> Literal["off", "once", "force"]:
    """
    RUN_BIRTHDAY_ON_START (opcional):
    - off / vazio / 0 / false: não faz nada extra ao subir (padrão)
    - 1, true, yes, on, sim, once: roda o job de aniversários uma vez ao conectar
    - force: zera quem já foi notificado hoje e roda o job (útil para testar de novo no mesmo dia)
    """
    raw = os.environ.get("RUN_BIRTHDAY_ON_START", "").strip().lower()
    if raw in ("", "0", "false", "no", "off", "não", "nao"):
        return "off"
    if raw in ("1", "true", "yes", "on", "sim", "once"):
        return "once"
    if raw == "force":
        return "force"
    return "off"


def _parse_birthday_mention() -> Literal["off", "everyone", "here"]:
    """
    BIRTHDAY_MENTION (opcional):
    - off / vazio: sem menção (padrão)
    - everyone: inclui @everyone na mensagem
    - here: inclui @here na mensagem
    """
    raw = os.environ.get("BIRTHDAY_MENTION", "").strip().lower()
    if raw in ("", "0", "false", "no", "off", "não", "nao", "none"):
        return "off"
    if raw in ("everyone", "all", "todos"):
        return "everyone"
    if raw in ("here", "online", "aqui"):
        return "here"
    return "off"


def load_config() -> Config:
    """
    Lê DISCORD_TOKEN, CHANNEL_ID e valida GROQ_API_KEY (obrigatória para o bot usar IA).

    TIMEZONE é opcional; padrão America/Sao_Paulo para o agendamento das 09:00.
    """
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    channel_raw = os.environ.get("CHANNEL_ID", "").strip()
    tz = os.environ.get("TIMEZONE", "America/Sao_Paulo").strip() or "America/Sao_Paulo"

    if not token:
        raise ValueError("Variável de ambiente DISCORD_TOKEN é obrigatória.")
    if not groq_key:
        raise ValueError("Variável de ambiente GROQ_API_KEY é obrigatória.")
    if not channel_raw:
        raise ValueError("Variável de ambiente CHANNEL_ID é obrigatória.")

    try:
        channel_id = int(channel_raw)
    except ValueError as exc:
        raise ValueError("CHANNEL_ID deve ser um número inteiro (ID do canal).") from exc

    return Config(
        discord_token=token,
        channel_id=channel_id,
        timezone=tz,
        run_birthday_on_start=_parse_run_birthday_on_start(),
        birthday_mention=_parse_birthday_mention(),
    )

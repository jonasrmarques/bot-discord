"""
Carrega e valida configuração a partir de variáveis de ambiente.

Use um arquivo .env na raiz (opcional) com python-dotenv em main.py,
ou defina as variáveis no sistema / painel do hospedeiro (Render, etc.).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Configuração imutável do bot após leitura do ambiente."""

    discord_token: str
    channel_id: int
    timezone: str


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
    )

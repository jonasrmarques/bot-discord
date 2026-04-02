"""
Persistência e regras de negócio dos aniversários.

Chaves no JSON seguem o formato MM-DD (mês-dia), conforme o enunciado:
ex.: comando DD-MM "02-04" (2 de abril) → chave "04-02".
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Caminhos relativos à raiz do projeto (onde main.py está)
ROOT = Path(__file__).resolve().parent.parent
BIRTHDAYS_FILE = ROOT / "birthdays.json"
STATE_FILE = ROOT / "birthday_state.json"


def _read_json(path: Path, default: Any) -> Any:
    """Lê JSON do disco; retorna default se o arquivo não existir ou estiver vazio."""
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Falha ao ler %s: %s", path, e)
        return default


def _write_json(path: Path, data: Any) -> None:
    """Grava JSON com indentação legível."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_birthdays() -> dict[str, list[str]]:
    """
    Retorna mapa MM-DD -> lista de nomes (texto livre, sem @).
    Garante que valores são listas de strings.
    """
    raw = _read_json(BIRTHDAYS_FILE, {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, list):
            out[k] = [str(x) for x in v]
        elif v is not None:
            out[k] = [str(v)]
    return out


def save_birthdays(data: dict[str, list[str]]) -> None:
    """Persiste o dicionário completo de aniversários."""
    _write_json(BIRTHDAYS_FILE, data)


def parse_dd_mm_to_key(fragment: str) -> str:
    """
    Converte fragmento DD-MM em chave MM-DD para armazenamento.
    Ex.: "02-04" -> "04-02" (2 de abril).
    """
    part = fragment.strip()
    if len(part) != 5 or part[2] != "-":
        raise ValueError("Use o formato DD-MM (ex.: 02-04).")
    day_s, month_s = part[:2], part[3:5]
    if not (day_s.isdigit() and month_s.isdigit()):
        raise ValueError("Dia e mês devem ser numéricos (DD-MM).")
    day, month = int(day_s), int(month_s)
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError("Data inválida.")
    # Valida calendário real (evita 31-02, etc.)
    try:
        datetime(2000, month, day)
    except ValueError as exc:
        raise ValueError("Data inválida para o mês indicado.") from exc
    return f"{month_s}-{day_s}"


def today_key(zone_name: str) -> str:
    """Retorna a chave MM-DD do dia atual no fuso informado."""
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(zone_name)).date()
    return f"{today.month:02d}-{today.day:02d}"


def add_birthday(nome: str, dd_mm: str) -> str:
    """
    Adiciona nome à lista do dia (comando em DD-MM).
    Retorna a chave MM-DD usada no JSON.
    """
    key = parse_dd_mm_to_key(dd_mm)
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("O nome não pode ser vazio.")
    data = load_birthdays()
    nomes = list(data.get(key, []))
    if nome_limpo not in nomes:
        nomes.append(nome_limpo)
    data[key] = nomes
    save_birthdays(data)
    logger.info("Aniversário salvo: nome=%s key=%s", nome_limpo, key)
    return key


def list_birthdays_formatted() -> list[tuple[str, list[str]]]:
    """
    Lista ordenada (MM-DD) com os nomes por data, para exibição no Discord.
    """
    data = load_birthdays()
    return sorted(data.items(), key=lambda x: x[0])


def get_birthday_names_for_key(key_mm_dd: str) -> list[str]:
    """Retorna cópia da lista de nomes para uma chave MM-DD."""
    data = load_birthdays()
    return list(data.get(key_mm_dd, []))


# --- Estado do dia (evita mensagem duplicada no mesmo dia) ---


def load_sent_state() -> tuple[str | None, set[str]]:
    """
    Retorna (data ISO do último reset, conjunto de chaves já parabenizadas nessa data).
    Formato da data: YYYY-MM-DD no fuso do agendamento.
    Compatível com estado antigo `sent_user_ids` (IDs) e novo `sent_recipients` (nomes).
    """
    raw = _read_json(STATE_FILE, {})
    if not isinstance(raw, dict):
        return None, set()
    d = raw.get("last_run_date")
    recipients = raw.get("sent_recipients")
    if not isinstance(recipients, list):
        recipients = raw.get("sent_user_ids", [])
    if not isinstance(d, str):
        d = None
    if isinstance(recipients, list):
        return d, {str(x) for x in recipients}
    return d, set()


def save_sent_state(run_date: str, sent: set[str]) -> None:
    """Persiste quem já recebeu mensagem na data run_date (YYYY-MM-DD)."""
    _write_json(
        STATE_FILE,
        {"last_run_date": run_date, "sent_recipients": sorted(sent)},
    )


def should_send_today(
    zone_name: str,
    recipient_key: str,
) -> tuple[bool, str, set[str]]:
    """
    Se a data mudou desde o último estado, limpa o conjunto em memória ao persistir.
    recipient_key é o nome (ou identificador) usado no JSON.
    Retorna (pode enviar, data_iso_hoje, conjunto_atualizado_em_memória).
    """
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(zone_name)).date()
    today_iso = today.isoformat()
    last_date, sent = load_sent_state()

    if last_date != today_iso:
        sent = set()
        save_sent_state(today_iso, sent)

    key = str(recipient_key)
    if key in sent:
        return False, today_iso, sent
    return True, today_iso, sent


def mark_sent(zone_name: str, recipient_key: str) -> None:
    """Marca destinatário como já notificado hoje (após envio bem-sucedido)."""
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(zone_name)).date()
    today_iso = today.isoformat()
    last_date, sent = load_sent_state()
    if last_date != today_iso:
        sent = set()
    sent.add(str(recipient_key))
    save_sent_state(today_iso, sent)

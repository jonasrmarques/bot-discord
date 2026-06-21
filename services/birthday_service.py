"""
Persistência e regras de negócio dos aniversários.

Chaves no JSON seguem o formato MM-DD (mês-dia), conforme o enunciado:
ex.: comando DD-MM "02-04" (2 de abril) → chave "04-02".
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

Sexo = Literal["masculino", "feminino"]


@dataclass(frozen=True)
class BirthdayPerson:
    nome: str
    sexo: Sexo

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


def normalize_sexo(value: str) -> Sexo:
    """Normaliza entrada de sexo (comando ou JSON legado)."""
    raw = value.strip().lower()
    if raw in ("f", "feminino", "fem"):
        return "feminino"
    if raw in ("m", "masculino", "masc"):
        return "masculino"
    raise ValueError("Sexo inválido. Use `masculino` ou `feminino` (ou `m` / `f`).")


def _parse_person_entry(entry: Any) -> BirthdayPerson | None:
    """Converte item do JSON em BirthdayPerson (aceita string legada ou objeto)."""
    if isinstance(entry, str):
        nome = entry.strip()
        if not nome:
            return None
        return BirthdayPerson(nome=nome, sexo="masculino")
    if isinstance(entry, dict):
        nome_raw = entry.get("nome", entry.get("name", ""))
        if not isinstance(nome_raw, str):
            return None
        nome = nome_raw.strip()
        if not nome:
            return None
        sexo_raw = entry.get("sexo", entry.get("genero", "masculino"))
        if not isinstance(sexo_raw, str):
            sexo_raw = "masculino"
        try:
            sexo = normalize_sexo(sexo_raw)
        except ValueError:
            sexo = "masculino"
        return BirthdayPerson(nome=nome, sexo=sexo)
    return None


def _person_to_json(person: BirthdayPerson) -> dict[str, str]:
    return {"nome": person.nome, "sexo": person.sexo}


def load_birthdays() -> dict[str, list[BirthdayPerson]]:
    """
    Retorna mapa MM-DD -> lista de aniversariantes (nome + sexo).
    Aceita JSON legado com lista de strings.
    """
    raw = _read_json(BIRTHDAYS_FILE, {})
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[BirthdayPerson]] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        entries: list[Any]
        if isinstance(v, list):
            entries = v
        elif v is not None:
            entries = [v]
        else:
            continue
        people: list[BirthdayPerson] = []
        for entry in entries:
            person = _parse_person_entry(entry)
            if person is not None:
                people.append(person)
        if people:
            out[k] = people
    return out


def save_birthdays(data: dict[str, list[BirthdayPerson]]) -> None:
    """Persiste o dicionário completo de aniversários."""
    serializable = {
        key: [_person_to_json(person) for person in people]
        for key, people in data.items()
    }
    _write_json(BIRTHDAYS_FILE, serializable)


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


def parse_add_birthday_text(texto: str) -> tuple[str, str, Sexo]:
    """
    Interpreta texto do comando !addbirthday.
    Formatos: `Nome DD-MM` ou `Nome DD-MM masculino|feminino`.
    """
    partes = texto.rsplit(maxsplit=2)
    if len(partes) == 3:
        nome, dd_mm, sexo_raw = partes[0].strip(), partes[1].strip(), partes[2].strip()
        sexo = normalize_sexo(sexo_raw)
        if not nome:
            raise ValueError("Informe o nome antes da data.")
        return nome, dd_mm, sexo
    if len(partes) == 2:
        nome, dd_mm = partes[0].strip(), partes[1].strip()
        if not nome:
            raise ValueError("Informe o nome antes da data.")
        return nome, dd_mm, "masculino"
    raise ValueError("Uso: `!addbirthday Nome DD-MM [masculino|feminino]`.")


def add_birthday(nome: str, dd_mm: str, sexo: Sexo = "masculino") -> str:
    """
    Adiciona aniversariante à lista do dia (comando em DD-MM).
    Retorna a chave MM-DD usada no JSON.
    """
    key = parse_dd_mm_to_key(dd_mm)
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("O nome não pode ser vazio.")
    person = BirthdayPerson(nome=nome_limpo, sexo=sexo)
    data = load_birthdays()
    people = list(data.get(key, []))
    if not any(p.nome == person.nome for p in people):
        people.append(person)
    data[key] = people
    save_birthdays(data)
    logger.info("Aniversário salvo: nome=%s sexo=%s key=%s", nome_limpo, sexo, key)
    return key


def list_birthdays_formatted() -> list[tuple[str, list[BirthdayPerson]]]:
    """
    Lista ordenada (MM-DD) com aniversariantes por data, para exibição no Discord.
    """
    data = load_birthdays()
    return sorted(data.items(), key=lambda x: x[0])


def get_birthdays_for_key(key_mm_dd: str) -> list[BirthdayPerson]:
    """Retorna cópia da lista de aniversariantes para uma chave MM-DD."""
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


def reset_sent_for_today(zone_name: str) -> None:
    """
    Zera a lista de destinatários já notificados hoje (só para testes com RUN_BIRTHDAY_ON_START=force).
    """
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo(zone_name)).date()
    today_iso = today.isoformat()
    save_sent_state(today_iso, set())
    logger.info("Estado de envios do dia %s foi zerado.", today_iso)


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

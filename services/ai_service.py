"""
Geração de mensagens de aniversário via API da Groq (SDK oficial).

A chave fica apenas em GROQ_API_KEY (variável de ambiente). Em qualquer falha
(rede, quota, resposta vazia, chave ausente), usamos mensagem padrão estável.
"""

from __future__ import annotations

import logging
import os
import random

from groq import Groq

logger = logging.getLogger(__name__)

# Padrão alinhado à Groq (llama3-70b-8192 foi descontinuado — ver console.groq.com/docs/deprecations)
MODELO_PADRAO = "llama-3.3-70b-versatile"

# Pequenas variações de “direção” para o modelo — reduz sensação de texto repetido
NUANCES_ESTILO = (
    "Prefira uma abertura inusitada antes de parabenizar.",
    "Inclua uma mini zoeira carinhosa no meio do texto.",
    "Termine com um twist humorístico bem leve.",
    "Misture um trocadilho bobo com o parabéns.",
    "Fale como quem tá no voice às 3h da manhã zoando o amigo.",
)


def mensagem_padrao(nome: str) -> str:
    """Resposta fixa quando a Groq não está disponível ou falha."""
    return f"🎉 Parabéns {nome}! Muitas felicidades!"


def _montar_prompt_usuario(nome: str) -> str:
    """
    Prompt principal + nuance aleatória para variar tom sem mudar a identidade do bot.

    O enunciado pede tom natural, engraçado, com humor leve, emojis e zoeira leve.
    """
    nuance = random.choice(NUANCES_ESTILO)
    return (
        "Crie uma mensagem de aniversário engraçada, estilo grupo de amigos no Discord.\n"
        "Use humor leve, emojis e uma pequena zoeira.\n\n"
        f"Nome da pessoa: {nome}\n\n"
        f"Variação de estilo (siga de forma natural): {nuance}\n\n"
        "Regras: no máximo 3 frases curtas; não use menções @ nem tags de usuário; "
        "não use hashtags; evite repetir a mesma estrutura de frases de um parabéns genérico."
    )


def gerar_mensagem(nome: str) -> str:
    """
    Gera texto de aniversário com a Groq. Nunca lança exceção por falha da API:
    em erro, retorna mensagem_padrao(nome).

    Cliente Groq autenticado com GROQ_API_KEY. Modelo padrão: llama-3.3-70b-versatile.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        logger.warning("GROQ_API_KEY não definida; usando mensagem padrão.")
        return mensagem_padrao(nome)

    modelo = os.environ.get("GROQ_MODEL", MODELO_PADRAO).strip() or MODELO_PADRAO

    try:
        # SDK oficial: mesma ideia de chat completions, endpoint Groq
        client = Groq(api_key=api_key)
        user_content = _montar_prompt_usuario(nome)

        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você escreve mensagens curtas de aniversário para amigos em servidores Discord. "
                        "Responda apenas com o texto da mensagem, em português."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            max_tokens=256,
            temperature=0.92,
        )

        choice = response.choices[0].message
        text = (getattr(choice, "content", None) or "").strip()
        if not text:
            logger.warning("Groq retornou conteúdo vazio para %s", nome)
            return mensagem_padrao(nome)

        logger.info("Mensagem de aniversário gerada via Groq para %s", nome)
        return text

    except Exception as e:
        # Falha esperada às vezes (modelo, quota, rede) → fallback sem traceback no console
        logger.warning("Groq não gerou texto para %s (%s); usando mensagem padrão.", nome, e)
        return mensagem_padrao(nome)

import re
import unicodedata


def remover_acentos(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def chave_ordenacao(nome: str) -> str:
    return remover_acentos(nome).casefold()


def gerar_slug(nome: str) -> str:
    slug = remover_acentos(nome).lower()
    # O portal remove o apóstrofo em vez de trocá-lo por hífen: D'Oeste -> doeste
    slug = re.sub(r"['’`]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")

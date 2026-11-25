import logging
import sys
from datetime import date

from playwright.sync_api import Error as PlaywrightError

from coleta_ibge import api, planilha
from coleta_ibge.extrator import extrair_dados
from coleta_ibge.navegador import ErroNavegacao, Navegador, PaginaNaoEncontrada, montar_url

LIMITE_PADRAO = 5

log = logging.getLogger("coleta_ibge")


def escolher_estado(estados: list[dict]) -> dict:
    for numero, estado in enumerate(estados, start=1):
        print(f"{numero:>2}) {estado['nome']} ({estado['sigla']})")

    por_sigla = {estado["sigla"]: estado for estado in estados}
    while True:
        escolha = input("\nEscolha o número ou a sigla da UF: ").strip().upper()
        if escolha in por_sigla:
            return por_sigla[escolha]
        if escolha.isdigit() and 1 <= int(escolha) <= len(estados):
            return estados[int(escolha) - 1]
        print(f"Opção inválida: '{escolha}'. Informe um número de 1 a {len(estados)} ou uma sigla da lista.")


def escolher_limite(total: int) -> int:
    padrao = min(LIMITE_PADRAO, total)
    while True:
        escolha = input(f"Quantidade de municípios [{padrao}] (máximo {total}): ").strip()
        if not escolha:
            return padrao
        if escolha.isdigit() and 1 <= int(escolha) <= total:
            return int(escolha)
        print(f"Quantidade inválida: '{escolha}'. Informe um número inteiro de 1 a {total}.")


def coletar_portal(estado: dict, municipios: list[dict]) -> tuple[list[dict], list[dict]]:
    registros, ocorrencias = [], []
    hoje = date.today()

    with Navegador() as navegador:
        for posicao, municipio in enumerate(municipios, start=1):
            url = montar_url(estado["sigla"], municipio["municipio"])
            log.info("[%d/%d] %s - %s", posicao, len(municipios), municipio["municipio"], url)

            dados = {}
            try:
                dados = extrair_dados(navegador.capturar_html(url))
            except PaginaNaoEncontrada as erro:
                log.warning("URL não encontrada: %s", url)
                ocorrencias.append({**municipio, "tipo": "url_nao_encontrada", "detalhe": str(erro)})
            except ErroNavegacao as erro:
                log.warning("Falha na navegação: %s", erro)
                ocorrencias.append({**municipio, "tipo": "erro_navegacao", "detalhe": str(erro)})

            registros.append({
                **municipio,
                "uf": estado["sigla"],
                "regiao": estado["regiao"],
                **dados,
                "url_fonte": url,
                "data_coleta": hoje,
            })

    return registros, ocorrencias


def executar() -> int:
    with api.criar_cliente() as cliente:
        estados = api.listar_estados(cliente)
        estado = escolher_estado(estados)

        municipios = api.listar_municipios(cliente, estado["sigla"])
        print(f"\n{estado['nome']} tem {len(municipios)} municípios na API de Localidades.")
        limite = escolher_limite(len(municipios))
        selecionados = municipios[:limite]

        log.info("UF escolhida: %s | municípios a processar: %d", estado["sigla"], len(selecionados))
        registros, ocorrencias = coletar_portal(estado, selecionados)
        df = planilha.montar_municipios(registros)

        falhas = {o["codigo_ibge"] for o in ocorrencias}
        ocorrencias += planilha.listar_ausencias(df, ignorar=falhas)

        pib = {}
        try:
            pib = api.buscar_pib(cliente, df["codigo_ibge"].tolist())
        except api.ErroAPI as erro:
            log.warning("PIB indisponível: %s", erro)
            ocorrencias.append({"codigo_ibge": "", "municipio": "", "tipo": "erro_agregados", "detalhe": str(erro)})

    resumo = {
        "uf": estado["sigla"],
        "estado": estado["nome"],
        "regiao": estado["regiao"],
        "municipios_na_uf": len(municipios),
        "municipios_processados": len(df),
        "paginas_coletadas": len(df) - len(falhas),
        "paginas_com_falha": len(falhas),
        "registros_com_dado_ausente": sum(o["tipo"] == "dado_ausente" for o in ocorrencias),
        "data_coleta": date.today().isoformat(),
        "fonte_pib": f"API de Agregados, tabela {api.TABELA_PIB}, variável {api.VARIAVEL_PIB}",
    }
    caminho = planilha.exportar(estado["sigla"], df, resumo, ocorrencias, planilha.montar_pib(df, pib))

    log.info(
        "Concluído: %s | %d municípios processados, %d com falha no portal | arquivo: %s",
        estado["sigla"], len(df), len(falhas), caminho,
    )
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        return executar()
    except api.ErroAPI as erro:
        log.error("Não foi possível consultar a API do IBGE: %s", erro)
    except PlaywrightError as erro:
        log.error("Não foi possível iniciar o navegador: %s", erro.message)
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.")
    except EOFError:
        print("\nEntrada encerrada antes da escolha.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

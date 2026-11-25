import time
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from coleta_ibge.texto import gerar_slug

URL_PORTAL = "https://www.ibge.gov.br/cidades-e-estados"
SELETOR_CONTEUDO = "div.indicador p.ind-value"

# O portal fica atrás de uma verificação da Cloudflare que não é liberada
# no modo headless, por isso o navegador abre visível.
HEADLESS = False


class PaginaNaoEncontrada(Exception):
    pass


class ErroNavegacao(Exception):
    pass


def montar_url(uf: str, municipio: str) -> str:
    return f"{URL_PORTAL}/{uf.lower()}/{gerar_slug(municipio)}.html"


class Navegador:
    def __init__(self, timeout_ms: int = 30_000, pausa_s: float = 1.5):
        self.timeout_ms = timeout_ms
        self.pausa_s = pausa_s

    def __enter__(self):
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=HEADLESS)
            self._context = self._browser.new_context(locale="pt-BR")
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.timeout_ms)
        except Exception:
            self._playwright.stop()
            raise
        return self

    def __exit__(self, *_):
        self._context.close()
        self._browser.close()
        self._playwright.stop()

    def capturar_html(self, url: str) -> str:
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self._page.wait_for_selector(SELETOR_CONTEUDO)
        except PlaywrightTimeoutError as erro:
            raise ErroNavegacao(f"O conteúdo de {url} não carregou a tempo") from erro
        except PlaywrightError as erro:
            raise ErroNavegacao(f"Falha ao abrir {url}: {erro.message}") from erro
        finally:
            time.sleep(self.pausa_s)

        # Para endereços inexistentes o portal não devolve 404: redireciona
        # para a página do Brasil, que também exibe indicadores.
        if urlparse(self._page.url).path != urlparse(url).path:
            raise PaginaNaoEncontrada(f"{url} redirecionou para {self._page.url}")
        return self._page.content()

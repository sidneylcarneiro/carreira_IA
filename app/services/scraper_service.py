"""
Serviço responsável por extrair o texto de uma vaga a partir de uma URL.

Utiliza a API pública do Jina Reader (https://r.jina.ai/) para contornar sites
com JavaScript e bloqueios, retornando o conteúdo já renderizado em Markdown.
"""
import httpx


class ScraperError(Exception):
    """Exceção levantada quando não é possível extrair o texto de uma URL."""


async def extrair_texto_da_url(url: str) -> str:
    """
    Extrai o texto limpo (em Markdown) de uma página web usando o Jina Reader.

    Args:
        url: URL completa da vaga (ex.: https://empresa.com.br/vagas/123).

    Returns:
        O conteúdo da página em texto/Markdown.

    Raises:
        ScraperError: Se a URL for inválida, o site estiver fora do ar ou
            bloquear acessos automáticos.
    """
    url = (url or "").strip()
    if not url:
        raise ScraperError("A URL informada está vazia.")

    if not (url.startswith("http://") or url.startswith("https://")):
        raise ScraperError(
            "A URL informada não é válida (deve começar com http:// ou https://)."
        )

    jina_url = f"https://r.jina.ai/{url}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/plain",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(jina_url, headers=headers)
            response.raise_for_status()
            texto = response.text
    except httpx.HTTPStatusError as e:
        raise ScraperError(f"O site retornou o status {e.response.status_code}.")
    except httpx.TimeoutException:
        raise ScraperError("Tempo de espera esgotado ao acessar a URL.")
    except httpx.RequestError as e:
        raise ScraperError(f"Falha de rede ao acessar a URL: {e}")

    if not texto.strip():
        raise ScraperError("O conteúdo extraído da página está vazio.")

    return texto

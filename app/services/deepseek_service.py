import httpx
import json
from ..config import settings

async def analisar_vaga_com_ia(texto_vaga: str) -> dict:
    """
    Analisa o texto de uma vaga usando a API do DeepSeek, extraindo dados estruturados
    no formato JSON especificado para ATS e currículo ideal.
    """
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY não está configurada nas definições do projeto")

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    system_prompt = """
    Atue como um Especialista em Recrutamento e ATS (Sistema de Rastreamento de Candidatos).
    Você deve retornar APENAS um JSON válido, sem nenhum texto adicional, comentário ou explicação.
    Ignore quaisquer ruídos no texto da vaga (como menus, propagandas, links, etc.).
    Extraia os dados da vaga respeitando exatamente a seguinte estrutura JSON:
    {
      "vaga": {
        "empresa": "nome_da_empresa",
        "titulo_vaga": "titulo_da_vaga",
        "modelo_trabalho": "Presencial/Remoto/Híbrido",
        "localidade": "cidade/estado ou null",
        "cultura_e_valores": ["lista", "de", "palavras-chave"],
        "atividades_principais": ["lista", "de", "principais_atividades"],
        "requisitos_tecnicos": ["lista", "de", "requisitos_tecnicos"],
        "requisitos_comportamentais": ["lista", "de", "requisitos_comportamentais"]
      },
      "curriculo_ideal": {
        "resumo_profissional_sugerido": "texto persuasivo e otimizado para ATS",
        "palavras_chave_ats": ["lista", "de", "termos", "essenciais"],
        "estruturas_de_experiencia": [
          {"dica_de_preenchimento": "como o candidato deve descrever a experiência x usando a palavra-chave y"}
        ]
      }
    }
    """

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_vaga}
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            response_json = response.json()
            content = response_json["choices"][0]["message"]["content"]
            
            # Parse the JSON content from the response
            resultado = json.loads(content)
            return resultado

    except httpx.HTTPStatusError as e:
        raise Exception(f"Falha na requisição à API do DeepSeek: Status {e.response.status_code} - {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Resposta JSON inválida do DeepSeek: {str(e)}")
    except KeyError as e:
        raise Exception(f"Campo faltante na resposta do DeepSeek: {str(e)}")
    except Exception as e:
        raise Exception(f"Erro inesperado ao analisar a vaga: {str(e)}")


import httpx
import json
from ..config import settings


async def _chamar_deepseek(system_prompt: str, user_content: str) -> dict:
    """Chama a API do DeepSeek e retorna o conteúdo JSON extraído da resposta."""
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY não está configurada nas definições do projeto")

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()

            response_json = response.json()
            content = response_json["choices"][0]["message"]["content"]

            # Parse do JSON retornado pela IA
            resultado = json.loads(content)
            return resultado

    except httpx.HTTPStatusError as e:
        raise Exception(f"Falha na requisição à API do DeepSeek: Status {e.response.status_code} - {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Resposta JSON inválida do DeepSeek: {str(e)}")
    except KeyError as e:
        raise Exception(f"Campo faltante na resposta do DeepSeek: {str(e)}")
    except Exception as e:
        raise Exception(f"Erro inesperado ao chamar o DeepSeek: {str(e)}")


async def analisar_vaga_com_ia(texto_vaga: str) -> dict:
    """
    Analisa o texto de uma vaga usando a API do DeepSeek, extraindo dados estruturados
    no formato JSON especificado para ATS e currículo ideal.
    """
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
    return await _chamar_deepseek(system_prompt, texto_vaga)


async def estruturar_curriculo_base(texto: str) -> dict:
    """
    Extrai os dados do currículo do usuário (texto bruto) para um JSON estruturado.

    Retorna um dict com dados_pessoais, resumo_profissional, experiencias, educacao e skills.
    """
    system_prompt = """
    Atue como um Especialista em Recrutamento e ATS.
    Você recebe o texto bruto do currículo de um candidato.
    Retorne APENAS um JSON válido, sem nenhum texto adicional, comentário ou explicação.

    Estruture o currículo respeitando exatamente a seguinte estrutura JSON:
    {
      "dados_pessoais": {
        "nome": "nome",
        "email": "email",
        "telefone": "telefone",
        "localizacao": "cidade/estado"
      },
      "resumo_profissional": "breve resumo profissional",
      "experiencias": [
        {"cargo": "...", "empresa": "...", "periodo": "...", "descricao": "..."}
      ],
      "educacao": [
        {"instituicao": "...", "curso": "...", "periodo": "..."}
      ],
      "skills": ["lista", "de", "habilidades"]
    }

    Regras:
    - NÃO invente informações. Se um campo não estiver no texto, use null ou lista vazia.
    - Mantenha os dados exatamente como aparecem no currículo.
    """
    return await _chamar_deepseek(system_prompt, texto)


async def adaptar_curriculo(curriculo_json: dict, vaga_json: dict) -> dict:
    """
    Cruza o currículo do candidato com a vaga e retorna um novo currículo adaptado
    e uma carta de apresentação, SEM inventar informações.

    Retorna um dict com curriculo_adaptado (JSON) e carta_apresentacao (string).
    """
    system_prompt = """
    Atue como um Consultor de Carreira e Especialista em ATS.
    Você recebe o CURRICULO BASE do candidato (JSON) e os dados de uma VAGA (JSON).
    Sua missão é adaptar o currículo para maximizar o "match" com a vaga.

    REGRAS DE OURO (obrigatórias e inegociáveis):
    1. NÃO MINTA. NÃO invente experiências, tecnologias, empresas, títulos, períodos
       ou habilidades que não existam no currículo base.
    2. Apenas REESCREVA e DESTAQUE as experiências reais que dão "match" com a vaga,
       usando palavras-chave presentes na vaga.
    3. NÃO crie qualificações falsas. Se o candidato não possui uma skill pedida,
       NÃO a adicione ao currículo.
    4. Use exclusivamente as informações do currículo base. Qualquer coisa que não
       esteja lá não deve aparecer.

    Retorne APENAS um JSON válido, sem nenhum texto adicional, no formato:
    {
      "curriculo_adaptado": {
        "dados_pessoais": {"nome": "...", "email": "...", "telefone": "...", "localizacao": "..."},
        "resumo_profissional": "resumo otimizado para a vaga, baseado apenas em fatos reais",
        "experiencias": [
          {"cargo": "...", "empresa": "...", "periodo": "...", "descricao_destacada": "reescrita destacando o match real"}
        ],
        "educacao": [{"instituicao": "...", "curso": "...", "periodo": "..."}],
        "skills_destaque": ["skills reais que dão match com a vaga"]
      },
      "carta_apresentacao": "carta de apresentação persuasiva, em primeira pessoa, 100% baseada nos fatos reais do currículo, sem inventar nada"
    }
    """
    user_content = (
        "CURRICULO BASE (dados reais do candidato):\n"
        f"{json.dumps(curriculo_json, ensure_ascii=False, indent=2)}\n\n"
        "VAGA (dados da vaga):\n"
        f"{json.dumps(vaga_json, ensure_ascii=False, indent=2)}"
    )
    return await _chamar_deepseek(system_prompt, user_content)


"""Teste manual do pipeline de dados (sem LLM).

Uso:
    python teste.py
"""

import json

from data_parser import get_aluno_origem, load_students, obter_conteudo_academico_hibrido


def rodar_teste():
    print("=" * 60)
    print("TESTE DO PIPELINE DE DADOS (SEM LLM)")
    print("=" * 60)

    alunos = load_students()
    if not alunos:
        print("Nenhum aluno carregado de academicData.ts")
        return

    aluno = alunos[0]
    nome = aluno["nome"]
    print(f"Aluno: {nome}")
    print(f"Defesa: {aluno['defesa']}")
    print(f"Origem: {get_aluno_origem(nome)}")

    conteudo = obter_conteudo_academico_hibrido(nome)
    if not conteudo:
        print("Nenhum conteúdo local encontrado (esperado se a coleta não estiver em dados/).")
        return

    print(f"Conteúdo local: {len(conteudo)} caracteres")
    print("-" * 60)
    print(json.dumps(
        {
            "nome": nome,
            "data_defesa": aluno["defesa"],
            "origem": get_aluno_origem(nome),
            "trecho": conteudo[:300],
        },
        indent=4,
        ensure_ascii=False,
    ))
    print("=" * 60)


if __name__ == "__main__":
    rodar_teste()

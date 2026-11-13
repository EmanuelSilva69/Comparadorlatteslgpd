# Privacidade e LGPD — inventário técnico

Este documento descreve **o que o sistema trata** e **onde cada dado fica**, para
apoiar a avaliação do Encarregado de Dados (DPO) da instituição. Não substitui
parecer jurídico: finalidade e base legal devem ser validadas pelo DPO.

## 1. Finalidade

Acompanhar a trajetória acadêmica e profissional dos egressos do mestrado em
Enfermagem, para fins de avaliação do programa e planejamento institucional.

## 2. Dados tratados e origem

| Dado | Origem | Onde fica | O site usa? |
|------|--------|-----------|-------------|
| Nome, data de defesa, situação, turma | formulários de inscrição / extração de PDFs do programa | `academicData.ts` | Sim |
| Resumo da trajetória pós-defesa | gerado a partir de Lattes/Escavador/PDFs | `resumos_cache.json` | Sim |
| Nome → fonte (Lattes/Escavador) | derivado dos arquivos de coleta | `indice_fontes.json` | Sim |
| Nome → ID Lattes / URL Escavador | Lattes / Escavador | `dados/mapeamento_lattes.json` | Não |
| Sexo e data de nascimento | formulário de inscrição | `dados/demographicData.ts` | **Não** |
| Páginas completas de perfil, e-mails de terceiros | Escavador | `dados/escavador_perfis/` | **Não** |
| Currículos completos | Lattes (scriptLattes) | `dados/scriptLattes/resultados/json/` | **Não** |
| Certificados pessoais | documentos do autor | `dados/CERTIFICADO_*.pdf` | **Não** |
| PDFs de inscrição do programa | formulários | fora do repositório | **Não** |

> Dados obtidos de fontes públicas (Lattes, Escavador) continuam sendo dados
> pessoais e exigem finalidade, necessidade e segurança (LGPD, art. 7º, §§ 3º e 4º).

## 3. Minimização aplicada

O site passou a depender apenas de três arquivos:

- `academicData.ts` — lista de alunos;
- `resumos_cache.json` — resumos exibidos;
- `indice_fontes.json` — índice derivado (nome → fonte).

Os HTMLs do Escavador, os JSONs do Lattes, as datas de nascimento/sexo e os PDFs
**não são mais necessários** para o funcionamento e ficaram fora do repositório e
da imagem Docker. O selo de origem na tela é obtido do índice.

## 4. Base legal e governança (a preencher com o DPO)

- Controlador: ______________________
- Encarregado (DPO): ______________________
- Base legal: ______________________ (ex.: legítimo interesse ou outra hipótese do art. 7º)
- Registro das operações de tratamento (ROPA): ______________________
- Prazo de retenção: ______________________
- Procedimento para atender titulares (acesso, correção, eliminação): ______________________

## 5. Segurança

- Acesso somente com login (individual ou mestre compartilhado, conforme decisão da equipe).
- Sessão em cookie `HttpOnly` e `SameSite=Strict`; logout invalida a sessão no servidor.
- Senhas em PBKDF2-SHA256; limite de tentativas de login.
- HTTPS no reverse proxy (obrigatório em produção).
- Aplicação escuta apenas em `127.0.0.1`; não é exposta diretamente.
- Container sem privilégio, filesystem somente leitura, sem GPU/LLM.
- Repositório **privado**; dados de coleta fora do Git.

## 6. Compartilhamento

Não há compartilhamento com terceiros nem transferência internacional. O sistema
não envia dados para serviços externos em tempo de execução.

## 7. Direitos dos titulares

Solicitações de acesso, correção ou eliminação devem ser encaminhadas ao DPO da
instituição. O sistema permite localizar o registro pelo nome do egresso.

## 8. Histórico

- Versão anterior: repositório público, API sem autenticação, LLM local com GPU.
- Versão atual: repositório privado, login obrigatório, sem LLM/GPU, dados de
  coleta fora do Git e fora da imagem.

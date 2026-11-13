/* Frontend do Comparador Lattes (versão sem LLM).
 * Todo dado vindo da API é inserido com textContent — nunca innerHTML. */

const API = "/api";

const estado = {
    alunos: [],
    cache: {},
};

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("buscaNome").addEventListener("input", filtrarTabela);
    document.getElementById("filtroOrigem").addEventListener("change", filtrarTabela);
    document.getElementById("filtroTurma").addEventListener("change", filtrarTabela);
    document.getElementById("btnRecarregar").addEventListener("click", recarregarResumos);
    document.getElementById("btnLogout").addEventListener("click", sair);
    document.getElementById("btnAtualizarLattes").addEventListener("click", () => dispararAtualizacao("lattes"));
    document.getElementById("btnAtualizarEscavador").addEventListener("click", () => dispararAtualizacao("escavador"));
    iniciar();
});

async function apiFetch(caminho, opcoes = {}) {
    const resposta = await fetch(API + caminho, {
        credentials: "same-origin",
        ...opcoes,
        headers: {
            "X-Requested-With": "XMLHttpRequest",
            ...(opcoes.headers || {}),
        },
    });

    if (resposta.status === 401) {
        window.location.href = "/login";
        throw new Error("Sessão expirada");
    }
    return resposta;
}

async function iniciar() {
    try {
        const [me, alunos, cache] = await Promise.all([
            apiFetch("/me").then((r) => r.json()),
            apiFetch("/alunos").then((r) => r.json()),
            apiFetch("/resumos-cache").then((r) => (r.ok ? r.json() : {})),
        ]);

        document.getElementById("usuarioAtual").textContent = me.usuario || "";

        if (!me.atualizacao) {
            document.getElementById("btnAtualizarLattes").hidden = true;
            document.getElementById("btnAtualizarEscavador").hidden = true;
        }

        estado.alunos = Array.isArray(alunos) ? alunos : [];
        estado.cache = cache && typeof cache === "object" ? cache : {};

        atualizarDashboard();
        popularFiltroTurma();
        renderizarTabela(estado.alunos);
    } catch (erro) {
        console.error(erro);
        mostrarAviso("Não foi possível carregar os dados. Verifique se a API está no ar.", true);
    }
}

function atualizarDashboard() {
    const total = estado.alunos.length;
    const jsonCount = estado.alunos.filter((a) => a.origem === "json").length;
    const htmlCount = estado.alunos.filter((a) => a.origem === "html").length;
    const noneCount = estado.alunos.filter((a) => a.origem === "none").length;

    document.getElementById("totalAlunos").textContent = total;
    document.getElementById("totalJson").textContent = jsonCount;
    document.getElementById("totalHtml").textContent = htmlCount;
    document.getElementById("totalNone").textContent = noneCount;
}

function popularFiltroTurma() {
    const select = document.getElementById("filtroTurma");
    const atual = select.value;

    while (select.options.length > 1) {
        select.remove(1);
    }

    const turmas = [...new Set(estado.alunos.map((a) => a.turma))].sort((a, b) => a - b);
    for (const turma of turmas) {
        const opcao = document.createElement("option");
        opcao.value = String(turma);
        opcao.textContent = `Turma ${turma}`;
        select.appendChild(opcao);
    }

    if ([...select.options].some((o) => o.value === atual)) {
        select.value = atual;
    }
}

function filtrarTabela() {
    const busca = document.getElementById("buscaNome").value.trim().toUpperCase();
    const origemFiltro = document.getElementById("filtroOrigem").value;
    const turmaFiltro = document.getElementById("filtroTurma").value;

    let filtrados = estado.alunos;

    if (busca) {
        filtrados = filtrados.filter((a) => a.nome.toUpperCase().includes(busca));
    }
    if (origemFiltro !== "todas") {
        filtrados = filtrados.filter((a) => a.origem === origemFiltro);
    }
    if (turmaFiltro !== "todas") {
        filtrados = filtrados.filter((a) => a.turma === parseInt(turmaFiltro, 10));
    }

    renderizarTabela(filtrados);
}

function renderizarTabela(alunos) {
    const container = document.getElementById("tabelaContainer");
    container.replaceChildren();

    if (alunos.length === 0) {
        const vazio = document.createElement("div");
        vazio.className = "vazio";
        vazio.textContent = "Nenhum aluno encontrado.";
        container.appendChild(vazio);
        return;
    }

    const turmas = new Map();
    for (const aluno of alunos) {
        const turma = aluno.turma || 0;
        if (!turmas.has(turma)) turmas.set(turma, []);
        turmas.get(turma).push(aluno);
    }

    for (const turma of [...turmas.keys()].sort((a, b) => a - b)) {
        container.appendChild(montarSecaoTurma(turma, turmas.get(turma)));
    }
}

function montarSecaoTurma(turma, alunos) {
    const secao = document.createElement("section");
    secao.className = "turma-section";

    const cabecalho = document.createElement("div");
    cabecalho.className = "turma-header";

    const titulo = document.createElement("span");
    titulo.textContent = `Turma ${turma}`;

    const contador = document.createElement("span");
    contador.className = "count";
    contador.textContent = `${alunos.length} aluno(s)`;

    cabecalho.append(titulo, contador);

    const tabela = document.createElement("table");

    const thead = document.createElement("thead");
    const linhaCabecalho = document.createElement("tr");
    for (const [texto, largura] of [["Nome", "35%"], ["Defesa", "15%"], ["Origem", "15%"], ["Resumo", "35%"]]) {
        const th = document.createElement("th");
        th.textContent = texto;
        th.style.width = largura;
        linhaCabecalho.appendChild(th);
    }
    thead.appendChild(linhaCabecalho);

    const tbody = document.createElement("tbody");
    for (const aluno of alunos) {
        tbody.appendChild(montarLinha(aluno));
    }

    tabela.append(thead, tbody);
    secao.append(cabecalho, tabela);
    return secao;
}

function montarLinha(aluno) {
    const tr = document.createElement("tr");

    const tdNome = document.createElement("td");
    const nome = document.createElement("strong");
    nome.className = "nome-aluno";
    nome.textContent = aluno.nome;
    tdNome.appendChild(nome);

    const tdDefesa = document.createElement("td");
    const defesa = document.createElement("span");
    const emAndamento = aluno.defesa === "EM ANDAMENTO";
    defesa.className = "defesa-label " + (emAndamento ? "defesa-em-andamento" : "defesa-concluida");
    defesa.textContent = aluno.defesa;
    tdDefesa.appendChild(defesa);

    const tdOrigem = document.createElement("td");
    const badge = document.createElement("span");
    const origem = aluno.origem;
    if (origem === "json") {
        badge.className = "badge badge-lattes";
        badge.textContent = "📄 JSON (Lattes)";
    } else if (origem === "html") {
        badge.className = "badge badge-escavador";
        badge.textContent = "🌐 HTML (Escavador)";
    } else {
        badge.className = "badge badge-none";
        badge.textContent = "— Nenhum";
    }
    tdOrigem.appendChild(badge);

    const tdResumo = document.createElement("td");
    tdResumo.className = "resumo-cell";
    const resumo = estado.cache[aluno.nome];
    if (typeof resumo === "string" && resumo.trim()) {
        const rotulo = document.createElement("span");
        rotulo.className = "resumo-label";
        rotulo.textContent = "Cache (sem LLM)";
        tdResumo.append(rotulo, document.createTextNode(resumo));
    } else {
        tdResumo.classList.add("resumo-placeholder");
        tdResumo.textContent = "Sem dados pós-defesa";
    }

    tr.append(tdNome, tdDefesa, tdOrigem, tdResumo);
    return tr;
}

async function recarregarResumos() {
    const botao = document.getElementById("btnRecarregar");
    botao.disabled = true;
    try {
        const resposta = await apiFetch("/resumos-cache");
        if (!resposta.ok) {
            mostrarAviso("Cache de resumos indisponível.", true);
            return;
        }
        const cache = await resposta.json();
        estado.cache = cache && typeof cache === "object" ? cache : {};
        filtrarTabela();

        const preenchidos = estado.alunos.filter((a) => {
            const valor = estado.cache[a.nome];
            return typeof valor === "string" && valor.trim();
        }).length;
        mostrarAviso(`Cache aplicado: ${preenchidos} resumo(s) preenchido(s).`);
    } catch (erro) {
        console.error(erro);
        mostrarAviso("Erro ao carregar o cache de resumos.", true);
    } finally {
        botao.disabled = false;
    }
}

async function dispararAtualizacao(alvo) {
    const nome = alvo === "lattes" ? "Lattes" : "Escavador";
    if (!window.confirm(`Iniciar a atualização do ${nome}?`)) return;

    try {
        const resposta = await apiFetch(`/update/${alvo}`, { method: "POST" });
        const dados = await resposta.json().catch(() => ({}));

        if (!resposta.ok) {
            mostrarAviso(dados.detail || "Não foi possível iniciar a atualização.", true);
            return;
        }
        mostrarAviso(dados.status || "Atualização iniciada.");
    } catch (erro) {
        console.error(erro);
        mostrarAviso("Erro ao acionar a atualização.", true);
    }
}

async function sair() {
    try {
        await apiFetch("/logout", { method: "POST" });
    } catch (erro) {
        console.error(erro);
    }
    window.location.href = "/login";
}

let toastTimer = null;

function mostrarAviso(mensagem, erro = false) {
    const toast = document.getElementById("toast");
    toast.textContent = mensagem;
    toast.classList.toggle("erro", Boolean(erro));
    toast.classList.add("visivel");

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visivel"), 6000);
}

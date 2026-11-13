/* Tela de login. A senha vai apenas para /api/login; a sessão fica em
 * cookie HttpOnly definido pelo servidor. */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("formLogin");
    const erro = document.getElementById("erroLogin");
    const botao = document.getElementById("btnEntrar");

    form.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        erro.textContent = "";

        const usuario = document.getElementById("usuario").value.trim();
        const senha = document.getElementById("senha").value;

        botao.disabled = true;
        botao.textContent = "Entrando...";

        try {
            const resposta = await fetch("/api/login", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({ usuario, senha }),
            });

            if (resposta.ok) {
                window.location.href = "/";
                return;
            }

            const dados = await resposta.json().catch(() => ({}));
            erro.textContent = dados.detail || "Não foi possível entrar.";
            document.getElementById("senha").value = "";
            document.getElementById("senha").focus();
        } catch (falha) {
            console.error(falha);
            erro.textContent = "Falha de comunicação com o servidor.";
        } finally {
            botao.disabled = false;
            botao.textContent = "Entrar";
        }
    });
});

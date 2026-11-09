/* ==========================================================================
   Ficha de Botticellius — lógica de front-end (JavaScript puro / Fetch API).

   Cada botão de ação carrega data-action e, quando aplicável, data-url.
   Ao clicar, dispara uma requisição POST para o endpoint correspondente,
   recebe o estado atualizado (JSON) e re-renderiza o dashboard em tempo real.
   ========================================================================== */

(function () {
    'use strict';

    // ----------------------------------------------------------------- CSRF
    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    // ----------------------------------------------------------------- Toast
    let toastTimer = null;
    function toast(message, isError) {
        const el = document.getElementById('toast');
        if (!el) return;
        el.textContent = message;
        el.classList.toggle('error', !!isError);
        el.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
    }

    // ------------------------------------------------------------- POST helper
    async function postAction(url, data) {
        const body = new URLSearchParams(data || {});
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: body.toString(),
        });
        let payload;
        try {
            payload = await response.json();
        } catch (e) {
            throw new Error('Resposta inválida do servidor.');
        }
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || 'Falha na ação.');
        }
        return payload;
    }

    // ------------------------------------------------------ Render do estado
    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function renderState(state) {
        if (!state) return;

        // Vida
        setText('hp-current', state.current_hp);
        setText('hp-max', state.max_hp);
        const fill = document.getElementById('hp-fill');
        if (fill) fill.style.width = state.hp_percent + '%';

        // CA / Defesa de Concha
        setText('ac-value', state.effective_ac);
        const shellBtn = document.getElementById('shell-btn');
        if (shellBtn) {
            shellBtn.classList.toggle('is-active', state.shell_defense_active);
            setText('shell-state', state.shell_defense_active ? '(ATIVA +4)' : '(inativa)');
        }

        // Recursos
        setText('cd-current', state.channel_divinity_current);
        setText('cd-max', state.channel_divinity_max);
        setText('eb-current', state.emboldening_bond_current);
        setText('eb-max', state.emboldening_bond_max);

        // Concentração
        const concBox = document.getElementById('conc-box');
        if (concBox) {
            const on = !!state.concentration_spell;
            concBox.classList.toggle('is-on', on);
            setText('conc-spell', on ? state.concentration_spell : '— Sem concentração ativa —');
        }

        // Espaços de magia
        (state.spell_slots || []).forEach((slot) => {
            const node = document.querySelector('.slot[data-level="' + slot.level + '"]');
            if (!node) return;
            const cur = node.querySelector('.slot-current');
            if (cur) cur.textContent = slot.current;
            const pips = node.querySelectorAll('.pip');
            pips.forEach((pip, idx) => pip.classList.toggle('spent', idx >= slot.current));
        });

        // Histórico de atividades
        if (state.logs) {
            const list = document.getElementById('log-list');
            if (list) {
                list.innerHTML = state.logs.map((l) =>
                    '<li><span class="log-when">' + l.when + '</span>' +
                    '<span class="log-action">' + escapeHtml(l.action) + '</span></li>'
                ).join('') || '<li class="log-empty">Nenhuma atividade registrada ainda.</li>';
            }
        }

        // Histórico de rolagens
        if (state.dice_rolls) {
            const dh = document.getElementById('dice-history');
            if (dh) {
                dh.innerHTML = state.dice_rolls.map((d) =>
                    '<li><span class="dh-dice">' + escapeHtml(d.dice) + '</span>' +
                    '<span class="dh-result">' + d.result + '</span>' +
                    '<span class="dh-when">' + d.when + '</span></li>'
                ).join('');
            }
        }
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function showRoll(roll) {
        if (!roll) return;
        const box = document.getElementById('last-roll');
        if (box) {
            box.textContent = roll.label + ': ' + roll.total + ' [' + roll.detail + ']';
            box.classList.remove('pop');
            void box.offsetWidth; // reinicia a animação
            box.classList.add('pop');
        }
        toast('🎲 ' + roll.label + ' → ' + roll.total);
    }

    // -------------------------------------------------------- Dispatcher
    async function handle(btn) {
        const action = btn.dataset.action;
        let url = btn.dataset.url;
        let data = {};

        switch (action) {
            case 'damage':
            case 'heal': {
                const amount = parseInt(document.getElementById('hp-amount').value, 10) || 0;
                data.amount = amount;
                break;
            }
            case 'roll-dice':
                data.dice = btn.dataset.dice;
                break;
            case 'roll-formula':
                data.formula = btn.dataset.formula;
                data.label = btn.dataset.label || btn.dataset.formula;
                break;
            case 'long-rest':
                if (!confirm('Confirmar Descanso Longo? Isso restaura PV, recursos e espaços de magia.')) {
                    return;
                }
                break;
            default:
                break;
        }

        // URLs para ações de rolagem que não têm data-url no HTML
        if (action === 'roll-dice') url = ROLL_DICE_URL;
        if (action === 'roll-formula') url = ROLL_FORMULA_URL;

        btn.disabled = true;
        try {
            const payload = await postAction(url, data);
            renderState(payload.state);
            if (payload.roll) showRoll(payload.roll);
            else feedbackFor(action, payload);
        } catch (err) {
            toast(err.message, true);
        } finally {
            btn.disabled = false;
        }
    }

    function feedbackFor(action, payload) {
        const messages = {
            'damage': 'Dano aplicado.',
            'heal': 'Cura aplicada.',
            'cast': payload.spell ? ('Conjurou ' + payload.spell + (payload.concentration ? ' (concentrando)' : '')) : 'Magia conjurada.',
            'generic': 'Ação registrada.',
            'shell-defense': 'Defesa de Concha atualizada.',
            'end-conc': 'Concentração encerrada.',
            'short-rest': 'Descanso curto concluído.',
            'long-rest': 'Descanso longo concluído.',
        };
        toast(messages[action] || 'Pronto.');
    }

    // ----------------------------------------------------- Upload da foto
    async function uploadAvatar(file) {
        const data = new FormData();
        data.append('avatar', file);
        const response = await fetch(UPLOAD_AVATAR_URL, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            body: data,
        });
        let payload;
        try {
            payload = await response.json();
        } catch (e) {
            throw new Error('Resposta inválida do servidor.');
        }
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || 'Falha ao enviar a foto.');
        }
        return payload;
    }

    function handleAvatarChange(input) {
        const file = input.files && input.files[0];
        if (!file) return;
        uploadAvatar(file).then((payload) => {
            const img = document.getElementById('avatar-img');
            const placeholder = document.getElementById('avatar-placeholder');
            // cache-bust para sempre exibir a imagem recém-enviada
            if (img) {
                img.src = payload.avatar_url + '?t=' + Date.now();
                img.hidden = false;
            }
            if (placeholder) placeholder.hidden = true;
            toast('📷 Foto atualizada.');
        }).catch((err) => {
            toast(err.message, true);
        }).finally(() => {
            input.value = '';
        });
    }

    // ---------------------------------------------------------- Bootstrap
    // URLs resolvidas pelo Django e injetadas em window.SHEET_URLS.
    const URLS = window.SHEET_URLS || {};
    const ROLL_DICE_URL = URLS.rollDice || '/api/roll-dice/';
    const ROLL_FORMULA_URL = URLS.rollFormula || '/api/roll-formula/';
    const UPLOAD_AVATAR_URL = URLS.uploadAvatar || '/api/avatar/';

    document.addEventListener('DOMContentLoaded', function () {
        // Delegação de eventos: um único listener para todos os botões.
        document.body.addEventListener('click', function (ev) {
            const btn = ev.target.closest('[data-action]');
            if (btn) {
                ev.preventDefault();
                handle(btn);
            }
        });

        // Upload da foto do personagem.
        const avatarInput = document.getElementById('avatar-input');
        if (avatarInput) {
            avatarInput.addEventListener('change', function () {
                handleAvatarChange(avatarInput);
            });
        }
    });
})();

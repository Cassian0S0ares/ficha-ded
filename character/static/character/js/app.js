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
        renderEffects(state.effects || []);

        // Desfazer
        const undoBtn = document.getElementById('undo-btn');
        if (undoBtn && 'undo_label' in state) {
            undoBtn.disabled = !state.undo_label;
            const text = state.undo_label ? 'Desfazer: ' + state.undo_label : 'Nada para desfazer';
            undoBtn.title = state.undo_label ? text + ' (Ctrl+Z)' : text;
            undoBtn.setAttribute('aria-label', text);
        }

        // Como as condições afetam as rolagens
        const rollEffects = document.getElementById('roll-effects');
        if (rollEffects && state.roll_effects) {
            rollEffects.innerHTML = state.roll_effects.map((l) => '<li>' + escapeHtml(l) + '</li>').join('');
            document.getElementById('roll-effects-box').hidden = !state.roll_effects.length;
        }

        // Vida
        setText('hp-current', state.current_hp);
        setText('hp-max', state.max_hp);
        renderVitality(state);
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

    // PV temporários, Dados de Vida e testes contra a morte
    function renderVitality(state) {
        if (!('temp_hp' in state)) return;
        const temp = document.getElementById('hp-temp');
        if (temp) temp.hidden = !state.temp_hp;
        setText('hp-temp-value', state.temp_hp);
        setText('hd-current', state.hit_dice_current);
        setText('hd-max', state.hit_dice_max);
        const hdBtn = document.getElementById('hd-btn');
        if (hdBtn) hdBtn.disabled = !state.hit_dice_current || state.is_dead;

        const box = document.getElementById('death-box');
        if (!box) return;
        box.hidden = !state.is_down;
        document.getElementById('hp-critical-label').hidden = !state.is_down;
        box.dataset.successes = state.death_successes;
        box.dataset.failures = state.death_failures;
        box.querySelectorAll('.death-pip').forEach((pip) => {
            const count = pip.dataset.kind === 'successes' ? state.death_successes : state.death_failures;
            const on = parseInt(pip.dataset.value, 10) <= count;
            pip.classList.toggle('is-on', on);
            pip.setAttribute('aria-pressed', String(on));
        });
        box.classList.toggle('is-dead', state.is_dead);
        box.classList.toggle('is-stable', state.is_stable);
        setText('death-status', state.is_dead
            ? 'Morto. Só magia como Reviver traz de volta.'
            : state.is_stable
                ? 'Estável: inconsciente, mas fora de perigo. Recupera 1 PV em 1d4 horas.'
                : 'Inconsciente. Role no início de cada turno: 10+ sucesso, 20 natural volta com 1 PV.');
        document.getElementById('death-roll-btn').hidden = state.is_dead || state.is_stable;
        document.getElementById('revive-btn').hidden = !state.is_dead;
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function showRoll(roll) {
        if (!roll) return;
        let text = roll.auto_fail
            ? roll.label + ': falha automática (' + roll.detail + ')'
            : roll.label + ': ' + roll.total + ' [' + roll.detail + ']';
        if (roll.critical) text += ' · 20 natural: CRÍTICO!';
        if (roll.fumble) text += ' · 1 natural: erro automático.';
        (roll.warnings || []).forEach((w) => { text += ' · Atenção: ' + w; });
        const box = document.getElementById('last-roll');
        if (box) {
            box.textContent = text;
            box.classList.remove('pop');
            void box.offsetWidth; // reinicia a animação
            box.classList.add('pop');
        }
        let summary = roll.auto_fail ? roll.label + ' → falha automática' : roll.label + ' → ' + roll.total;
        if (roll.mode === 'advantage') summary += ' (com vantagem)';
        if (roll.mode === 'disadvantage') summary += ' (com desvantagem)';
        if (roll.critical) summary += ' · CRÍTICO!';
        toast(summary, roll.auto_fail || roll.fumble);
    }

    function showConcentrationSave(save) {
        let message;
        if (save.unconscious) {
            message = 'Caiu a 0 PV: concentração em ' + save.spell + ' perdida.';
        } else {
            message = 'Salv. CON ' + save.total + ' vs CD ' + save.dc + ' [' + save.detail.replace(/ vs CD \d+$/, '') + ']: ' +
                (save.success ? 'concentração em ' + save.spell + ' mantida.' : 'concentração em ' + save.spell + ' perdida!');
        }
        const box = document.getElementById('conc-save');
        if (box) {
            box.textContent = message;
            box.classList.toggle('is-success', !!save.success);
            box.classList.toggle('is-fail', !save.success);
        }
        toast(message, !save.success);
    }

    // -------------------------------------------------------- Dispatcher
    async function handle(btn) {
        const action = btn.dataset.action;
        let url = btn.dataset.url;
        let data = {};

        switch (action) {
            case 'effect-toggle':
                data = {key: btn.dataset.key, toggle: '1'};
                break;
            case 'effect-save': {
                const row = btn.closest('.effect-row');
                const rounds = row.querySelector('[name=rounds]');
                if (!rounds.checkValidity()) { rounds.reportValidity(); return; }
                data = {key: btn.dataset.key, rounds: rounds.value,
                    level: row.querySelector('[name=level]')?.value || '1'};
                break;
            }
            case 'damage':
            case 'heal': {
                const amount = parseInt(document.getElementById('hp-amount').value, 10) || 0;
                data.amount = amount;
                const critical = document.getElementById('hp-critical');
                if (action === 'damage' && critical && critical.checked) {
                    data.critical = '1';
                    critical.checked = false;
                }
                break;
            }
            case 'temp-hp':
                data.amount = parseInt(document.getElementById('temp-amount').value, 10) || 0;
                break;
            case 'death-set': {
                // Clicar na marca acesa mais alta apaga ela; senão acende até ela.
                const box = document.getElementById('death-box');
                const value = parseInt(btn.dataset.value, 10);
                const counts = { successes: parseInt(box.dataset.successes, 10) || 0,
                                 failures: parseInt(box.dataset.failures, 10) || 0 };
                counts[btn.dataset.kind] = counts[btn.dataset.kind] === value ? value - 1 : value;
                Object.assign(data, counts);
                url = URLS.deathSet;
                break;
            }
            case 'roll-dice':
                data.dice = btn.dataset.dice;
                break;
            case 'roll-d20':
                data.kind = btn.dataset.kind;
                data.ability = btn.dataset.ability;
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
        if (action === 'roll-d20') url = ROLL_D20_URL;

        btn.disabled = true;
        try {
            const payload = await postAction(url, data);
            renderState(payload.state);
            if (payload.inventory && window.SheetInventory) window.SheetInventory.set(payload.inventory);
            if (payload.undone) { toast('Desfeito: ' + payload.undone); return; }
            if (payload.effect_notices?.length) {
                document.getElementById('effect-alerts').textContent = payload.effect_notices.join(' ');
                toast(payload.effect_notices.join(' '));
                return;
            }
            if (payload.roll) showRoll(payload.roll);
            else if (payload.conc_save) showConcentrationSave(payload.conc_save);
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
            'temp-hp': 'PV temporários atualizados.',
            'death-set': 'Testes contra a morte ajustados.',
            'revive': 'De volta à vida com 1 PV.',
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

    function renderEffects(effects) {
        const list = document.getElementById('active-effects');
        if (!list) return;
        document.querySelectorAll('[data-action="effect-toggle"]').forEach(btn => {
            const on = effects.some(e => e.key === btn.dataset.key);
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-pressed', String(on));
        });
        list.innerHTML = effects.map(e => {
            const warning = e.rounds !== null && e.rounds <= 2;
            return '<div class="effect-row' + (warning ? ' effect-warning' : '') + '">' +
                '<div><strong>' + escapeHtml(e.name) + '</strong>' +
                (e.key === 'exhaustion' ? ' · Nível ' + e.level : '') +
                '<p>' + escapeHtml(e.description) + '</p>' +
                (warning ? '<strong>Está para acabar!</strong>' : '') + '</div>' +
                '<div class="effect-controls"><label>Rodadas <input name="rounds" type="number" min="1" max="100000" step="1" placeholder="Sem prazo" value="' + (e.rounds ?? '') + '"></label>' +
                (e.key === 'exhaustion' ? '<label>Nível <select name="level">' + [1,2,3,4,5,6].map(n => '<option' + (n === e.level ? ' selected' : '') + '>' + n + '</option>').join('') + '</select></label>' : '') +
                '<button class="btn btn-sm" data-action="effect-save" data-key="' + e.key + '" data-url="' + URLS.effectChange + '">Salvar</button>' +
                '<button class="btn btn-sm" data-action="effect-toggle" data-key="' + e.key + '" data-url="' + URLS.effectChange + '">Encerrar</button></div></div>';
        }).join('') || '<p>Nenhuma condição ou efeito ativo.</p>';
        document.getElementById('effect-alerts').textContent = effects.filter(e => e.rounds !== null && e.rounds <= 2)
            .map(e => e.name + ': restam ' + e.rounds + ' rodada(s)!').join(' ');
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
            toast('Foto atualizada.');
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
    const ROLL_D20_URL = URLS.rollD20 || '/api/roll-d20/';
    const UPLOAD_AVATAR_URL = URLS.uploadAvatar || '/api/avatar/';

    // Exposto para outros módulos (ex.: inventário) atualizarem a ficha.
    window.SheetApp = { renderState: renderState };

    document.addEventListener('DOMContentLoaded', function () {
        const initial = document.getElementById('sheet-initial-state');
        if (initial) renderState(JSON.parse(initial.textContent));
        // Delegação de eventos: um único listener para todos os botões.
        document.body.addEventListener('click', function (ev) {
            const btn = ev.target.closest('[data-action]');
            if (btn) {
                ev.preventDefault();
                handle(btn);
            }
        });

        // Ctrl+Z desfaz a última ação (fora de campos de texto e janelas abertas).
        document.addEventListener('keydown', function (ev) {
            if (!(ev.ctrlKey || ev.metaKey) || ev.shiftKey || ev.altKey || ev.key.toLowerCase() !== 'z') return;
            const el = document.activeElement;
            if (el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName))) return;
            if (document.querySelector('dialog[open], .notes-drawer.is-open')) return;
            const btn = document.getElementById('undo-btn');
            if (btn && !btn.disabled) {
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

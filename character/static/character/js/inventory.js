/* ==========================================================================
   Inventário — itens agrupados por categoria e moedas.

   Cada ação faz POST para /api/inventory/... e recebe o inventário completo,
   que é re-renderizado. Itens com fórmula de dano ganham um botão "Rolar"
   que usa o handler de rolagem do app.js (data-action="roll-formula").
   ========================================================================== */

(function () {
    'use strict';

    const BASE = (window.SHEET_URLS || {}).inventory || '/api/inventory/';
    const $ = (id) => document.getElementById(id);

    let data = { coins: [], items: [], categories: [] };
    let editingId = null;     // null = novo item
    let confirmDelete = null; // id aguardando o segundo clique em "Apagar"

    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function toast(message, isError) {
        const el = $('toast');
        if (!el) return;
        el.textContent = message;
        el.classList.toggle('error', !!isError);
        el.classList.add('show');
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => el.classList.remove('show'), 2600);
    }

    async function post(path, body) {
        const response = await fetch(BASE + path, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(body || {}).toString(),
        });
        let payload;
        try {
            payload = await response.json();
        } catch (e) {
            throw new Error('Resposta inválida do servidor.');
        }
        if (!response.ok || !payload.ok) throw new Error(payload.error || 'Falha na ação.');
        data = payload.inventory;
        render();
        // Mantém o histórico de atividades da ficha em dia.
        if (payload.state && window.SheetApp) window.SheetApp.renderState(payload.state);
        return payload;
    }

    async function run(fn) {
        try {
            await fn();
        } catch (err) {
            toast(err.message, true);
        }
    }

    const itemById = (id) => data.items.find((i) => i.id === id);

    // ------------------------------------------------------------ Render
    function itemRow(item) {
        const id = item.id;
        const empty = item.quantity === 0;
        let actions = '';
        if (item.category === 'consumable') {
            actions += '<button type="button" class="btn btn-xs btn-heal" data-inv="use" data-id="' + id + '"' +
                (empty ? ' disabled' : '') + '>Usar</button>';
        }
        if (item.damage_formula) {
            actions += '<button type="button" class="btn btn-xs btn-damage" data-action="roll-formula" data-formula="' +
                escapeHtml(item.damage_formula) + '" data-label="' + escapeHtml(item.name) + '">Rolar ' +
                escapeHtml(item.damage_formula) + '</button>';
        }
        actions += '<button type="button" class="btn btn-xs" data-inv="edit" data-id="' + id + '">Editar</button>';
        actions += '<button type="button" class="btn btn-xs ' + (confirmDelete === id ? 'btn-damage' : 'btn-ghost inv-delete') +
            '" data-inv="delete" data-id="' + id + '">' + (confirmDelete === id ? 'Confirmar?' : 'Apagar') + '</button>';

        return '<li class="inv-item' + (empty ? ' is-empty' : '') + (item.equipped ? ' is-equipped' : '') + '">' +
            '<div class="inv-item-main">' +
            '<span class="inv-item-name">' + escapeHtml(item.name) + '</span>' +
            (item.equipped ? '<span class="inv-badge">Equipado</span>' : '') +
            (item.description ? '<p class="inv-item-desc">' + escapeHtml(item.description) + '</p>' : '') +
            '</div>' +
            '<div class="inv-qty" role="group" aria-label="Quantidade de ' + escapeHtml(item.name) + '">' +
            '<button type="button" class="inv-qty-btn" data-inv="qty" data-delta="-1" data-id="' + id + '" aria-label="Menos um"' +
            (empty ? ' disabled' : '') + '>−</button>' +
            '<span class="inv-qty-value">' + item.quantity + '</span>' +
            '<button type="button" class="inv-qty-btn" data-inv="qty" data-delta="1" data-id="' + id + '" aria-label="Mais um">+</button>' +
            '</div>' +
            '<div class="inv-item-actions">' + actions + '</div>' +
            '</li>';
    }

    function render() {
        const list = $('inv-list');
        if (!data.items.length) {
            list.innerHTML = '<p class="inv-empty">Inventário vazio. Use “+ Item” para adicionar.</p>';
        } else {
            list.innerHTML = data.categories.map((cat) => {
                const items = data.items.filter((i) => i.category === cat.key);
                if (!items.length) return '';
                return '<div class="inv-group"><h3 class="spell-group-title">' + escapeHtml(cat.label) +
                    ' <span class="inv-count">' + items.length + '</span></h3>' +
                    '<ul>' + items.map(itemRow).join('') + '</ul></div>';
            }).join('');
        }
        data.coins.forEach((coin) => {
            const input = document.querySelector('.inv-coins input[name="' + coin.field + '"]');
            if (input && document.activeElement !== input) input.value = coin.amount;
        });
    }

    // ------------------------------------------------------- Formulário
    function openForm(item) {
        const form = $('inv-form');
        editingId = item ? item.id : null;
        $('inv-form-title').textContent = item ? 'Editar ' + item.name : 'Novo item';
        form.elements.name.value = item ? item.name : '';
        form.elements.category.value = item ? item.category : 'gear';
        form.elements.quantity.value = item ? item.quantity : 1;
        form.elements.damage_formula.value = item ? item.damage_formula : '';
        form.elements.equipped.checked = item ? item.equipped : false;
        form.elements.description.value = item ? item.description : '';
        form.hidden = false;
        form.elements.name.focus();
    }

    function closeForm() {
        $('inv-form').hidden = true;
        editingId = null;
    }

    async function submitForm(ev) {
        ev.preventDefault();
        const form = $('inv-form');
        const name = form.elements.name.value.trim();
        if (!name) {
            form.elements.name.setCustomValidity('Informe o nome do item.');
            form.elements.name.reportValidity();
            form.elements.name.setCustomValidity('');
            return;
        }
        if (!form.elements.quantity.checkValidity()) {
            form.elements.quantity.reportValidity();
            return;
        }
        const body = {
            name: name,
            category: form.elements.category.value,
            quantity: form.elements.quantity.value,
            damage_formula: form.elements.damage_formula.value.trim(),
            description: form.elements.description.value,
        };
        if (form.elements.equipped.checked) body.equipped = 'on';
        else if (editingId) body.equipped = '';
        await run(async () => {
            const wasEditing = editingId;
            await post(wasEditing ? wasEditing + '/' : 'new/', body);
            closeForm();
            toast(wasEditing ? 'Item atualizado.' : 'Item adicionado.');
        });
    }

    // ------------------------------------------------------------ Ações
    const actions = {
        'new': () => openForm(null),
        'cancel': closeForm,
        'edit': (btn) => openForm(itemById(parseInt(btn.dataset.id, 10))),
        'qty': (btn) => run(() => post(btn.dataset.id + '/quantity/', { delta: btn.dataset.delta })),
        'use': (btn) => run(async () => {
            const item = itemById(parseInt(btn.dataset.id, 10));
            await post(btn.dataset.id + '/use/');
            const left = itemById(item.id);
            toast('Usou ' + item.name + '. Restam ' + (left ? left.quantity : 0) + '.');
        }),
        'delete': (btn) => {
            const id = parseInt(btn.dataset.id, 10);
            if (confirmDelete !== id) {
                confirmDelete = id;
                render();
                setTimeout(() => { if (confirmDelete === id) { confirmDelete = null; render(); } }, 4000);
                return;
            }
            confirmDelete = null;
            run(async () => {
                const item = itemById(id);
                await post(id + '/delete/');
                if (editingId === id) closeForm();
                toast((item ? item.name : 'Item') + ' removido.');
            });
        },
    };

    document.addEventListener('DOMContentLoaded', function () {
        const card = $('inventory');
        if (!card) return;
        try {
            data = JSON.parse($('inventory-data').textContent);
        } catch (e) { /* mantém vazio */ }
        render();
        // Permite que outras partes da ficha (ex.: Desfazer) atualizem a lista.
        window.SheetInventory = { set: (inventory) => { data = inventory; render(); } };

        card.addEventListener('click', (ev) => {
            const btn = ev.target.closest('[data-inv]');
            if (btn && actions[btn.dataset.inv]) actions[btn.dataset.inv](btn);
        });
        $('inv-form').addEventListener('submit', submitForm);

        card.querySelectorAll('.inv-coins input').forEach((input) => {
            input.addEventListener('change', () => {
                if (!input.checkValidity() || input.value === '') {
                    input.reportValidity();
                    return;
                }
                run(() => post('coins/', { [input.name]: input.value }));
            });
        });
    });
})();

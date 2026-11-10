/* ==========================================================================
   Personagens da campanha — gaveta lateral com foto, afeto (0 a 3) e notas.

   Cada ação faz POST para /api/npcs/... e recebe a lista completa, que é
   re-renderizada. Nome e anotações são salvos automaticamente ao digitar;
   a pesquisa filtra pelo nome (sem diferenciar acentos e maiúsculas).
   ========================================================================== */

(function () {
    'use strict';

    const BASE = (window.SHEET_URLS || {}).npcs || '/api/npcs/';
    const SAVE_DELAY = 700;
    const MAX_AFFECTION = 3;

    let npcs = [];
    let currentId = null;
    let saveTimer = null;
    let pending = {};
    let confirmDelete = false;
    let loaded = false;

    const $ = (id) => document.getElementById(id);

    // ----------------------------------------------------------- Helpers
    function getCsrfToken() {
        const input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    const fold = (str) => String(str).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

    function toast(message, isError) {
        const el = $('toast');
        if (!el) return;
        el.textContent = message;
        el.classList.toggle('error', !!isError);
        el.classList.add('show');
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => el.classList.remove('show'), 2600);
    }

    async function request(path, body) {
        const options = { headers: { 'X-Requested-With': 'XMLHttpRequest' } };
        if (body) {
            options.method = 'POST';
            options.headers['X-CSRFToken'] = getCsrfToken();
            if (body instanceof FormData) {
                options.body = body;
            } else {
                options.headers['Content-Type'] = 'application/x-www-form-urlencoded';
                options.body = new URLSearchParams(body).toString();
            }
        }
        const response = await fetch(BASE + path, options);
        let payload;
        try {
            payload = await response.json();
        } catch (e) {
            throw new Error('Resposta inválida do servidor.');
        }
        if (!response.ok || !payload.ok) throw new Error(payload.error || 'Falha na ação.');
        npcs = payload.npcs;
        return payload;
    }

    async function run(fn) {
        try {
            await fn();
        } catch (err) {
            toast(err.message, true);
        }
    }

    const npcById = (id) => npcs.find((n) => n.id === id);

    function hearts(value) {
        return '♥'.repeat(value) + '♡'.repeat(MAX_AFFECTION - value);
    }

    // ------------------------------------------------------------ Render
    function renderList() {
        const query = fold($('npc-search').value.trim());
        const shown = npcs
            .filter((n) => !query || fold(n.name).includes(query))
            .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR', { sensitivity: 'base' }));
        const list = $('npc-list');
        if (!npcs.length) {
            list.innerHTML = '<li class="notes-list-empty">Nenhum personagem ainda.</li>';
            return;
        }
        if (!shown.length) {
            list.innerHTML = '<li class="notes-list-empty">Nenhum personagem com esse nome.</li>';
            return;
        }
        list.innerHTML = shown.map((n) =>
            '<li><button type="button" class="npc-item' + (n.id === currentId ? ' is-active' : '') +
            '" data-npc="open" data-id="' + n.id + '">' +
            (n.photo
                ? '<img class="npc-thumb" src="' + escapeHtml(n.photo) + '" alt="">'
                : '<span class="npc-thumb npc-thumb-empty" aria-hidden="true">' + escapeHtml(n.name.charAt(0).toUpperCase()) + '</span>') +
            '<span class="npc-item-name">' + escapeHtml(n.name) + '</span>' +
            '<span class="npc-item-hearts" aria-label="Afeto ' + n.affection + ' de 3">' + hearts(n.affection) + '</span>' +
            '</button></li>'
        ).join('');
    }

    function renderAffection(value) {
        document.querySelectorAll('.npc-affection-btn').forEach((btn) => {
            const on = parseInt(btn.dataset.value, 10) === value;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('aria-checked', String(on));
        });
        $('npc-hearts').textContent = hearts(value);
    }

    function renderPhoto(npc) {
        const img = $('npc-photo-img');
        img.hidden = !npc.photo;
        if (npc.photo) img.src = npc.photo;
        else img.removeAttribute('src');
        img.alt = npc.photo ? 'Foto de ' + npc.name : '';
        $('npc-photo-placeholder').hidden = !!npc.photo;
    }

    function renderEditor() {
        const npc = npcById(currentId);
        $('npc-form').hidden = !npc;
        $('npc-empty').hidden = !!npc;
        $('npc-drawer').classList.toggle('is-editing', !!npc);
        confirmDelete = false;
        $('npc-delete').textContent = 'Apagar personagem';
        if (!npc) return;
        $('npc-name').value = npc.name;
        $('npc-notes').value = npc.notes;
        renderAffection(npc.affection);
        renderPhoto(npc);
        $('npc-status').textContent = 'Salvo ' + npc.updated;
    }

    function render() {
        renderList();
        renderEditor();
    }

    // ----------------------------------------------------- Salvamento
    function queueSave(fields) {
        Object.assign(pending, fields);
        $('npc-status').textContent = 'Editando…';
        clearTimeout(saveTimer);
        saveTimer = setTimeout(flush, SAVE_DELAY);
    }

    async function flush() {
        clearTimeout(saveTimer);
        if (!currentId || !Object.keys(pending).length) return;
        const id = currentId;
        const fields = pending;
        pending = {};
        $('npc-status').textContent = 'Salvando…';
        try {
            await request(id + '/', fields);
            renderList();
            const npc = npcById(id);
            if (npc && id === currentId) $('npc-status').textContent = 'Salvo ' + npc.updated;
        } catch (err) {
            pending = Object.assign(fields, pending);
            $('npc-status').textContent = 'Não salvo';
            toast(err.message, true);
        }
    }

    function flushOnExit() {
        if (!currentId || !Object.keys(pending).length) return;
        const form = new FormData();
        Object.entries(pending).forEach(([k, v]) => form.append(k, v));
        form.append('csrfmiddlewaretoken', getCsrfToken());
        navigator.sendBeacon(BASE + currentId + '/', form);
        pending = {};
    }

    // ------------------------------------------------------------ Ações
    async function openNpc(id) {
        await flush();
        currentId = id;
        render();
    }

    const actions = {
        'close': () => setOpen(false),
        'back': async () => { await flush(); currentId = null; render(); },
        'open': (btn) => openNpc(parseInt(btn.dataset.id, 10)),
        'new': () => run(async () => {
            await flush();
            const typed = $('npc-search').value.trim();
            const payload = await request('new/', { name: typed || 'Novo personagem' });
            $('npc-search').value = '';
            await openNpc(payload.npc_id);
            $('npc-name').focus();
            $('npc-name').select();
        }),
        'affection': (btn) => run(async () => {
            const value = parseInt(btn.dataset.value, 10);
            renderAffection(value);
            await flush();
            await request(currentId + '/', { affection: value });
            renderList();
            const npc = npcById(currentId);
            if (npc) $('npc-status').textContent = 'Salvo ' + npc.updated;
        }),
        'delete': () => {
            const npc = npcById(currentId);
            if (!npc) return;
            if (!confirmDelete) {
                confirmDelete = true;
                $('npc-delete').textContent = 'Confirmar? Apaga ' + npc.name;
                setTimeout(() => {
                    if (confirmDelete && currentId === npc.id) {
                        confirmDelete = false;
                        $('npc-delete').textContent = 'Apagar personagem';
                    }
                }, 4000);
                return;
            }
            run(async () => {
                pending = {};
                clearTimeout(saveTimer);
                await request(npc.id + '/delete/', {});
                currentId = null;
                render();
                toast(npc.name + ' removido.');
            });
        },
    };

    function uploadPhoto(input) {
        const file = input.files && input.files[0];
        if (!file || !currentId) return;
        const form = new FormData();
        form.append('avatar', file);
        run(async () => {
            await flush();
            await request(currentId + '/photo/', form);
            render();
            toast('Foto atualizada.');
        }).finally(() => { input.value = ''; });
    }

    // ------------------------------------------------- Abrir/fechar gaveta
    function setOpen(open) {
        const drawer = $('npc-drawer');
        const tab = $('npc-tab');
        if (!open) {
            flush();
            drawer.classList.remove('is-open');
            tab.setAttribute('aria-expanded', 'false');
            setTimeout(() => { if (!drawer.classList.contains('is-open')) drawer.hidden = true; }, 300);
            tab.focus();
            return;
        }
        drawer.hidden = false;
        void drawer.offsetWidth; // permite a transição de entrada
        drawer.classList.add('is-open');
        tab.setAttribute('aria-expanded', 'true');
        if (!loaded) {
            run(async () => {
                await request('');
                loaded = true;
                render();
            });
        }
        $('npc-search').focus();
    }

    document.addEventListener('DOMContentLoaded', function () {
        const drawer = $('npc-drawer');
        if (!drawer) return;

        $('npc-tab').addEventListener('click', () => setOpen(!drawer.classList.contains('is-open')));
        drawer.addEventListener('click', (ev) => {
            const btn = ev.target.closest('[data-npc]');
            if (btn && actions[btn.dataset.npc]) actions[btn.dataset.npc](btn);
        });

        $('npc-search').addEventListener('input', renderList);
        $('npc-search').addEventListener('keydown', (ev) => {
            if (ev.key !== 'Enter') return;
            const first = $('npc-list').querySelector('[data-npc="open"]');
            if (first) openNpc(parseInt(first.dataset.id, 10));
        });
        $('npc-name').addEventListener('input', (ev) => {
            if (ev.target.value.trim()) queueSave({ name: ev.target.value.trim() });
        });
        $('npc-name').addEventListener('blur', (ev) => {
            const npc = npcById(currentId);
            if (npc && !ev.target.value.trim()) ev.target.value = npc.name;
            flush();
        });
        $('npc-notes').addEventListener('input', (ev) => queueSave({ notes: ev.target.value }));
        $('npc-notes').addEventListener('blur', flush);
        $('npc-photo-input').addEventListener('change', (ev) => uploadPhoto(ev.target));

        document.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape' && drawer.classList.contains('is-open') && !document.querySelector('dialog[open]')) {
                setOpen(false);
            }
        });
        window.addEventListener('pagehide', flushOnExit);
    });
})();

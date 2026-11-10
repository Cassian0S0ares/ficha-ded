/* ==========================================================================
   Notas da sessão — gaveta lateral com pastas e blocos de notas.

   Cada ação faz POST para /api/notes/... e recebe de volta a lista completa
   de pastas e blocos ({folders, notes}), que é re-renderizada. O conteúdo
   do bloco aberto é salvo automaticamente enquanto se digita.
   ========================================================================== */

(function () {
    'use strict';

    const BASE = (window.SHEET_URLS || {}).notes || '/api/notes/';
    const SAVE_DELAY = 700;
    const OPEN_KEY = 'notes:open-note';

    let data = { folders: [], notes: [] };
    let currentId = null;
    let saveTimer = null;
    let saving = null;
    let pending = {};          // campos alterados ainda não enviados
    const collapsed = new Set(); // pastas recolhidas

    const $ = (id) => document.getElementById(id);

    function ask(title, value = '', message = '', confirmation = false) {
        const dialog = $('notes-dialog');
        if (dialog.open) return Promise.resolve(null);
        const input = $('notes-dialog-input');
        const previousFocus = document.activeElement;
        $('notes-dialog-title').textContent = title;
        $('notes-dialog-message').textContent = message;
        $('notes-dialog-message').hidden = !message;
        $('notes-dialog-label').hidden = confirmation;
        input.hidden = confirmation;
        input.required = !confirmation;
        input.value = value;
        input.setCustomValidity('');
        $('notes-dialog-submit').textContent = confirmation ? 'Apagar' : 'Salvar';
        $('notes-dialog-submit').classList.toggle('btn-damage', confirmation);
        dialog.returnValue = '';
        return new Promise(resolve => {
            const form = $('notes-dialog-form');
            const submit = ev => {
                ev.preventDefault();
                if (!confirmation && !input.value.trim()) {
                    input.setCustomValidity('Informe um nome.');
                    input.reportValidity();
                    return;
                }
                dialog.close('save');
            };
            form.addEventListener('submit', submit);
            dialog.addEventListener('close', () => {
                form.removeEventListener('submit', submit);
                if (previousFocus?.isConnected) previousFocus.focus();
                resolve(dialog.returnValue === 'save' ? (confirmation ? true : input.value.trim()) : null);
            }, {once: true});
            dialog.showModal();
            if (confirmation) $('notes-dialog-cancel').focus();
            else { input.focus(); input.select(); }
        });
    }

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

    function toast(message, isError) {
        const el = $('toast');
        if (!el) return;
        el.textContent = message;
        el.classList.toggle('error', !!isError);
        el.classList.add('show');
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => el.classList.remove('show'), 2600);
    }

    function remember(id) {
        try {
            if (id) localStorage.setItem(OPEN_KEY, String(id));
            else localStorage.removeItem(OPEN_KEY);
        } catch (e) { /* armazenamento indisponível */ }
    }

    function remembered() {
        try { return parseInt(localStorage.getItem(OPEN_KEY), 10) || null; }
        catch (e) { return null; }
    }

    async function request(path, body) {
        const options = { headers: { 'X-Requested-With': 'XMLHttpRequest' } };
        if (body) {
            options.method = 'POST';
            options.headers['X-CSRFToken'] = getCsrfToken();
            options.headers['Content-Type'] = 'application/x-www-form-urlencoded';
            options.body = new URLSearchParams(body).toString();
        }
        const response = await fetch(BASE + path, options);
        let payload;
        try {
            payload = await response.json();
        } catch (e) {
            throw new Error('Resposta inválida do servidor.');
        }
        if (!response.ok || !payload.ok) {
            throw new Error(payload.error || 'Falha na ação.');
        }
        data = payload.notes;
        return payload;
    }

    const noteById = (id) => data.notes.find((n) => n.id === id);

    // ------------------------------------------------------------ Render
    function noteItem(n) {
        return '<li><button type="button" draggable="true" title="Arraste para mover para uma pasta" class="notes-item' +
            (n.id === currentId ? ' is-active' : '') +
            '" data-notes="open" data-id="' + n.id + '">' +
            '<span class="notes-item-title">' + escapeHtml(n.title) + '</span>' +
            '<span class="notes-item-when">' + n.updated + '</span></button></li>';
    }

    function renderTree() {
        const tree = $('notes-tree');
        let html = '';

        data.folders.forEach((f) => {
            const notes = data.notes.filter((n) => n.folder_id === f.id);
            const open = !collapsed.has(f.id);
            html += '<div data-drop-folder="' + f.id + '" class="notes-folder' + (open ? ' is-open' : '') + '">' +
                '<div class="notes-folder-head">' +
                '<button type="button" class="notes-folder-name" data-notes="toggle-folder" data-id="' + f.id +
                '" aria-expanded="' + open + '"><span class="notes-caret">▸</span>' + escapeHtml(f.name) +
                ' <span class="notes-count">' + notes.length + '</span></button>' +
                '<button type="button" class="notes-icon-btn" data-notes="new-note" data-folder="' + f.id +
                '" title="Novo bloco nesta pasta" aria-label="Novo bloco em ' + escapeHtml(f.name) + '">+</button>' +
                '<button type="button" class="notes-icon-btn" data-notes="rename-folder" data-id="' + f.id +
                '" title="Renomear pasta" aria-label="Renomear ' + escapeHtml(f.name) + '">✎</button>' +
                '<button type="button" class="notes-icon-btn is-danger" data-notes="delete-folder" data-id="' + f.id +
                '" title="Apagar pasta" aria-label="Apagar ' + escapeHtml(f.name) + '">🗑</button>' +
                '</div>' +
                (open ? '<ul class="notes-list">' + (notes.map(noteItem).join('') ||
                    '<li class="notes-list-empty">Pasta vazia</li>') + '</ul>' : '') +
                '</div>';
        });

        const loose = data.notes.filter((n) => !n.folder_id);
        {
            html += '<div class="notes-folder is-open is-root" data-drop-folder="">' +
                '<div class="notes-root-title">Sem pasta</div>' +
                '<ul class="notes-list">' + (loose.map(noteItem).join('') ||
                    '<li class="notes-list-empty">Nenhum bloco de notas ainda.</li>') + '</ul></div>';
        }
        tree.innerHTML = html;
    }

    function renderFolderSelect(note) {
        const select = $('note-folder');
        select.innerHTML = '<option value="">Sem pasta</option>' + data.folders.map((f) =>
            '<option value="' + f.id + '">' + escapeHtml(f.name) + '</option>').join('');
        select.value = note.folder_id ? String(note.folder_id) : '';
    }

    function renderEditor() {
        const note = noteById(currentId);
        $('notes-form').hidden = !note;
        $('notes-empty').hidden = !!note;
        $('notes-drawer').classList.toggle('is-editing', !!note);
        if (!note) return;
        $('note-title').value = note.title;
        $('note-content').value = note.content;
        renderFolderSelect(note);
        $('note-status').textContent = 'Salvo ' + note.updated;
    }

    function render() {
        renderTree();
        renderEditor();
    }

    // ----------------------------------------------------- Salvamento
    function queueSave(fields) {
        Object.assign(pending, fields);
        $('note-status').textContent = 'Editando…';
        clearTimeout(saveTimer);
        saveTimer = setTimeout(flush, SAVE_DELAY);
    }

    async function flush() {
        clearTimeout(saveTimer);
        if (saving) {
            await saving;
            if (Object.keys(pending).length) return flush();
            return;
        }
        saving = savePending();
        try { await saving; }
        finally { saving = null; }
    }

    async function savePending() {
        if (!currentId || !Object.keys(pending).length) return;
        const id = currentId;
        const fields = pending;
        pending = {};
        $('note-status').textContent = 'Salvando…';
        try {
            await request(id + '/', fields);
            renderTree();
            const note = noteById(id);
            if (note && id === currentId) $('note-status').textContent = 'Salvo ' + note.updated;
        } catch (err) {
            pending = Object.assign(fields, pending);
            $('note-status').textContent = 'Não salvo';
            toast(err.message, true);
        }
    }

    // Ao fechar/sair da página, envia o que faltar mesmo sem esperar resposta.
    function flushOnExit() {
        if (!currentId || !Object.keys(pending).length) return;
        const form = new FormData();
        Object.entries(pending).forEach(([k, v]) => form.append(k, v));
        form.append('csrfmiddlewaretoken', getCsrfToken());
        navigator.sendBeacon(BASE + currentId + '/', form);
        pending = {};
    }

    // ------------------------------------------------------- Ações
    async function openNote(id) {
        await flush();
        currentId = id;
        remember(id);
        render();
        $('note-content').focus();
    }

    async function run(fn) {
        try {
            await fn();
        } catch (err) {
            toast(err.message, true);
        }
    }

    const actions = {
        'close': () => setOpen(false),
        'back': async () => { await flush(); currentId = null; remember(null); render(); },
        'open': (btn) => openNote(parseInt(btn.dataset.id, 10)),
        'toggle-folder': (btn) => {
            const id = parseInt(btn.dataset.id, 10);
            if (collapsed.has(id)) collapsed.delete(id); else collapsed.add(id);
            renderTree();
        },
        'new-note': (btn) => run(async () => {
            const title = await ask('Novo bloco de notas', 'Sessão ' + new Date().toLocaleDateString('pt-BR'));
            if (!title || !title.trim()) return;
            await flush();
            const payload = await request('new/', { name: title.trim(), folder: btn.dataset.folder || '' });
            if (btn.dataset.folder) collapsed.delete(parseInt(btn.dataset.folder, 10));
            await openNote(payload.note_id);
        }),
        'new-folder': () => run(async () => {
            const name = await ask('Nova pasta');
            if (!name || !name.trim()) return;
            await request('folders/new/', { name: name.trim() });
            render();
            toast('Pasta criada.');
        }),
        'rename-folder': (btn) => run(async () => {
            const folder = data.folders.find((f) => f.id === parseInt(btn.dataset.id, 10));
            const name = await ask('Renomear pasta', folder ? folder.name : '');
            if (!name || !name.trim()) return;
            await request('folders/' + btn.dataset.id + '/rename/', { name: name.trim() });
            render();
            toast('Pasta renomeada.');
        }),
        'delete-folder': (btn) => run(async () => {
            const id = parseInt(btn.dataset.id, 10);
            const folder = data.folders.find((f) => f.id === id);
            const count = data.notes.filter((n) => n.folder_id === id).length;
            const msg = 'Apagar a pasta "' + (folder ? folder.name : '') + '"' +
                (count ? ' e os ' + count + ' bloco(s) de notas dentro dela' : '') +
                '? Isso não pode ser desfeito.';
            if (!await ask('Apagar pasta', '', msg, true)) return;
            const current = noteById(currentId);
            if (current && current.folder_id === id) { pending = {}; currentId = null; remember(null); }
            await request('folders/' + id + '/delete/', {});
            render();
            toast('Pasta apagada.');
        }),
        'delete-note': () => run(async () => {
            const note = noteById(currentId);
            if (!note || !await ask('Apagar bloco', '', 'Apagar o bloco "' + note.title + '"? Isso não pode ser desfeito.', true)) return;
            pending = {};
            clearTimeout(saveTimer);
            await request(note.id + '/delete/', {});
            currentId = null;
            remember(null);
            render();
            toast('Bloco de notas apagado.');
        }),
    };

    // ------------------------------------------------- Abrir/fechar gaveta
    let loaded = false;

    function setOpen(open) {
        const drawer = $('notes-drawer');
        const tab = $('notes-tab');
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
                const last = remembered();
                currentId = last && noteById(last) ? last : null;
                render();
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        const drawer = $('notes-drawer');
        if (!drawer) return;
        $('notes-dialog-cancel').addEventListener('click', () => $('notes-dialog').close());
        $('notes-dialog-input').addEventListener('input', ev => ev.target.setCustomValidity(''));

        let draggedId = null;
        let moving = false;
        const tree = $('notes-tree');
        const clearDrop = () => tree.querySelectorAll('.is-drop-target').forEach(el => el.classList.remove('is-drop-target'));
        tree.addEventListener('dragstart', ev => {
            const item = ev.target.closest('[data-notes="open"]');
            if (!item || moving) { ev.preventDefault(); return; }
            draggedId = Number(item.dataset.id);
            ev.dataTransfer.setData('text/plain', String(draggedId));
            ev.dataTransfer.effectAllowed = 'move';
            item.classList.add('is-dragging');
        });
        tree.addEventListener('dragover', ev => {
            const folder = ev.target.closest('[data-drop-folder]');
            if (!folder || !draggedId || moving) return;
            ev.preventDefault();
            ev.dataTransfer.dropEffect = 'move';
            clearDrop();
            folder.classList.add('is-drop-target');
        });
        tree.addEventListener('dragleave', ev => {
            const folder = ev.target.closest('[data-drop-folder]');
            if (folder && !folder.contains(ev.relatedTarget)) folder.classList.remove('is-drop-target');
        });
        tree.addEventListener('dragend', () => {
            draggedId = null;
            clearDrop();
            tree.querySelectorAll('.is-dragging').forEach(el => el.classList.remove('is-dragging'));
        });
        tree.addEventListener('drop', ev => {
            const folder = ev.target.closest('[data-drop-folder]');
            if (!folder || !draggedId || moving) return;
            ev.preventDefault();
            const id = draggedId;
            const folderId = folder.dataset.dropFolder;
            draggedId = null;
            clearDrop();
            const note = noteById(id);
            if (!note || String(note.folder_id || '') === folderId) return;
            moving = true;
            run(async () => {
                try {
                    await flush();
                    if (Object.keys(pending).length) throw new Error('Salve as alterações do bloco antes de movê-lo.');
                    await request(id + '/', {folder: folderId});
                    if (folderId) collapsed.delete(Number(folderId));
                    renderTree();
                    const current = noteById(currentId);
                    if (current) renderFolderSelect(current);
                    toast('Bloco movido.');
                } finally { moving = false; }
            });
        });

        $('notes-tab').addEventListener('click', () => setOpen(!drawer.classList.contains('is-open')));

        drawer.addEventListener('click', function (ev) {
            const btn = ev.target.closest('[data-notes]');
            if (btn && actions[btn.dataset.notes]) actions[btn.dataset.notes](btn);
        });

        $('note-content').addEventListener('input', (ev) => queueSave({ content: ev.target.value }));
        $('note-title').addEventListener('input', (ev) => {
            if (ev.target.value.trim()) queueSave({ title: ev.target.value.trim() });
        });
        $('note-title').addEventListener('blur', (ev) => {
            const note = noteById(currentId);
            if (note && !ev.target.value.trim()) ev.target.value = note.title;
            flush();
        });
        $('note-content').addEventListener('blur', flush);
        $('note-folder').addEventListener('change', (ev) => {
            const folder = ev.target.value;
            if (folder) collapsed.delete(parseInt(folder, 10));
            queueSave({ folder: folder });
            flush();
        });

        document.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape' && !$('notes-dialog').open && drawer.classList.contains('is-open')) setOpen(false);
        });
        window.addEventListener('pagehide', flushOnExit);
    });
})();

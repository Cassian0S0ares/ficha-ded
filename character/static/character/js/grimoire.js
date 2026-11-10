/* ==========================================================================
   Grimório — busca de magias pelo nome (sem diferenciar acentos/maiúsculas).

   1º tenta casar cada palavra digitada com o começo de uma palavra do nome
   ("cura" → "Curar Ferimentos"). Se nada bater, faz busca aproximada:
   cada palavra digitada precisa casar com o começo de alguma palavra do
   nome, tolerando letras erradas, faltando, sobrando ou trocadas de lugar
   (1 erro em palavras de 4–5 letras, 2 erros a partir de 6). Grafias de
   mesmo som (ch/x, ss/ç/s, z/s, qu/k, h mudo…) não contam como erro.
   Filtra os cards já renderizados; grupos sem resultado ficam ocultos.
   ========================================================================== */

(function () {
    'use strict';

    const fold = (str) => String(str).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    const words = (str) => str.split(/[^a-z0-9]+/).filter(Boolean);

    // Aproxima grafias de mesmo som no português (ex.: "flexa" ~ "flecha").
    function phonetic(word) {
        return word
            .replace(/ch/g, 'x').replace(/sh/g, 'x')
            .replace(/ph/g, 'f').replace(/qu/g, 'k').replace(/c(?=[ei])/g, 's')
            .replace(/ss|sc(?=[ei])|z/g, 's').replace(/y/g, 'i').replace(/w/g, 'v')
            .replace(/^h/, '').replace(/(.)\1+/g, '$1');
    }

    // Distância de edição com transposição de letras vizinhas (Damerau/OSA).
    function editDistance(a, b) {
        const rows = [];
        for (let i = 0; i <= a.length; i++) {
            rows.push([i]);
            for (let j = 1; j <= b.length; j++) {
                if (i === 0) { rows[0].push(j); continue; }
                const cost = a[i - 1] === b[j - 1] ? 0 : 1;
                let d = Math.min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + cost);
                if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
                    d = Math.min(d, rows[i - 2][j - 2] + 1);
                }
                rows[i].push(d);
            }
        }
        return rows[a.length][b.length];
    }

    function allowedErrors(term) {
        if (term.length >= 6) return 2;
        if (term.length >= 4) return 1;
        return 0;
    }

    // Erros entre o termo e o começo da palavra (aceita palavra ainda incompleta).
    function prefixDistance(term, word) {
        let best = Infinity;
        const max = allowedErrors(term);
        for (let len = term.length - max; len <= term.length + max; len++) {
            if (len < 1 || len > word.length) continue;
            best = Math.min(best, editDistance(term, word.slice(0, len)));
        }
        if (word.length < term.length - max) return best;
        return Math.min(best, editDistance(term, word));
    }

    function fuzzyMatch(queryTerms, nameWords) {
        return queryTerms.every((term) => {
            const sound = phonetic(term);
            return nameWords.some((word) =>
                prefixDistance(term, word) <= allowedErrors(term) ||
                prefixDistance(sound, phonetic(word)) <= allowedErrors(sound));
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        const input = document.getElementById('spell-search');
        if (!input) return;
        const groups = Array.from(document.querySelectorAll('#spell-groups .spell-group'));
        const spells = Array.from(document.querySelectorAll('#spell-groups .spell')).map((el) => {
            const name = fold(el.querySelector('.spell-name').textContent);
            return { el, name, words: words(name) };
        });
        const count = document.getElementById('spell-search-count');
        const empty = document.getElementById('spell-search-empty');

        function filter() {
            const query = fold(input.value.trim());
            const terms = words(query);
            let matches = spells.filter((s) => !query || terms.every((term) =>
                s.words.some((word) => word.startsWith(term))));
            let approximate = false;
            if (query && !matches.length) {
                matches = terms.length ? spells.filter((s) => fuzzyMatch(terms, s.words)) : [];
                approximate = matches.length > 0;
            }
            const shown = new Set(matches);
            spells.forEach((s) => { s.el.hidden = !shown.has(s); });
            groups.forEach((group) => {
                group.hidden = !group.querySelector('.spell:not([hidden])');
            });
            empty.hidden = matches.length > 0;
            count.textContent = query
                ? matches.length + ' de ' + spells.length + (approximate ? ' · aproximado' : '')
                : '';
        }

        input.addEventListener('input', filter);
        input.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape' && input.value) {
                ev.stopPropagation();
                input.value = '';
                filter();
            }
        });
    });
})();

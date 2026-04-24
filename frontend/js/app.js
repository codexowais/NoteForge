/**
 * NoteForge — Main Application
 */

(function () {
    'use strict';

    // ── DOM refs ────────────────────────────────────────────
    const $ = (s) => document.querySelector(s);
    const views = { landing: $('#landingView'), loading: $('#loadingView'), notes: $('#notesView'), error: $('#errorView') };
    const urlForm = $('#urlForm'), urlInput = $('#urlInput'), submitBtn = $('#submitBtn');
    const notesList = $('#notesList'), emptyState = $('#emptyState'), searchInput = $('#searchInput');
    const sidebar = $('#sidebar'), sidebarOverlay = $('#sidebarOverlay');
    const loadingStep = $('#loadingStep'), progressBar = $('#progressBar');
    const notesHeader = $('#notesHeader'), notesActions = $('#notesActions'), notesContent = $('#notesContent');
    const errorMessage = $('#errorMessage'), retryBtn = $('#retryBtn');
    const toastContainer = $('#toastContainer');
    const ollamaStatus = $('#ollamaStatus');

    let allNotes = [];
    let activeNoteId = null;

    // ── Init ────────────────────────────────────────────────
    async function init() {
        urlForm.addEventListener('submit', onSubmit);
        $('#newNoteBtn').addEventListener('click', showLanding);
        $('#mobileMenuBtn').addEventListener('click', toggleSidebar);
        sidebarOverlay.addEventListener('click', closeSidebar);
        retryBtn.addEventListener('click', showLanding);
        searchInput.addEventListener('input', renderSidebar);
        await loadNotes();
        checkHealth();
    }

    // ── Views ───────────────────────────────────────────────
    function showView(name) {
        Object.entries(views).forEach(([k, v]) => v.classList.toggle('active', k === name));
    }

    function showLanding() {
        activeNoteId = null;
        highlightActive();
        showView('landing');
        urlInput.value = '';
        urlInput.focus();
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        showView('error');
    }

    // ── Submit ──────────────────────────────────────────────
    async function onSubmit(e) {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (!url) return;

        showView('loading');
        submitBtn.disabled = true;
        animateProgress();

        try {
            const note = await api.generateNotes(url);
            await loadNotes();
            activeNoteId = note.id;
            renderNote(note);
            showView('notes');
            toast('Notes generated successfully!', 'success');
        } catch (err) {
            showError(err.message);
            toast(err.message, 'error');
        } finally {
            submitBtn.disabled = false;
            resetProgress();
        }
    }

    // ── Progress animation ──────────────────────────────────
    let progressInterval;
    const steps = [
        'Extracting transcript from YouTube...',
        'Sending transcript to AI model...',
        'Generating structured notes...',
        'Almost done — formatting output...',
    ];

    function animateProgress() {
        let pct = 0, step = 0;
        progressBar.style.width = '0%';
        loadingStep.textContent = steps[0];
        progressInterval = setInterval(() => {
            pct = Math.min(pct + Math.random() * 3 + 0.5, 92);
            progressBar.style.width = pct + '%';
            const newStep = Math.min(Math.floor(pct / 25), steps.length - 1);
            if (newStep !== step) { step = newStep; loadingStep.textContent = steps[step]; }
        }, 600);
    }

    function resetProgress() {
        clearInterval(progressInterval);
        progressBar.style.width = '100%';
        setTimeout(() => { progressBar.style.width = '0%'; }, 400);
    }

    // ── Sidebar ─────────────────────────────────────────────
    async function loadNotes() {
        try { allNotes = await api.listNotes(); } catch { allNotes = []; }
        renderSidebar();
    }

    function renderSidebar() {
        const q = searchInput.value.toLowerCase();
        const filtered = q ? allNotes.filter(n => n.title.toLowerCase().includes(q)) : allNotes;

        if (!filtered.length) {
            notesList.innerHTML = '';
            notesList.appendChild(emptyState);
            emptyState.style.display = 'block';
            return;
        }
        emptyState.style.display = 'none';

        notesList.innerHTML = filtered.map(n => `
            <div class="note-item ${n.id === activeNoteId ? 'active' : ''}" data-id="${n.id}">
                <div class="note-item-info">
                    <div class="note-item-title">${esc(n.title)}</div>
                    <div class="note-item-date">${fmtDate(n.created_at)}</div>
                </div>
                <button class="note-item-delete" data-id="${n.id}" title="Delete">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/></svg>
                </button>
            </div>
        `).join('');

        notesList.querySelectorAll('.note-item').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.note-item-delete')) return;
                openNote(el.dataset.id);
            });
        });
        notesList.querySelectorAll('.note-item-delete').forEach(btn => {
            btn.addEventListener('click', (e) => { e.stopPropagation(); deleteNote(btn.dataset.id); });
        });
    }

    function highlightActive() { renderSidebar(); }

    async function openNote(id) {
        try {
            const note = await api.getNote(id);
            activeNoteId = id;
            renderNote(note);
            showView('notes');
            highlightActive();
            closeSidebar();
        } catch (err) { toast('Failed to load note', 'error'); }
    }

    async function deleteNote(id) {
        if (!confirm('Delete this note?')) return;
        try {
            await api.deleteNote(id);
            toast('Note deleted', 'success');
            if (activeNoteId === id) showLanding();
            await loadNotes();
        } catch { toast('Failed to delete', 'error'); }
    }

    function toggleSidebar() { sidebar.classList.toggle('open'); sidebarOverlay.classList.toggle('active'); }
    function closeSidebar() { sidebar.classList.remove('open'); sidebarOverlay.classList.remove('active'); }

    // ── Render Note ─────────────────────────────────────────
    function renderNote(note) {
        const vid = note.video_id || '';
        const thumb = vid ? `https://img.youtube.com/vi/${vid}/hqdefault.jpg` : '';

        notesHeader.innerHTML = `
            <div class="notes-header-inner">
                ${thumb ? `<img class="notes-thumb" src="${thumb}" alt="Video thumbnail" onerror="this.style.display='none'">` : ''}
                <div class="notes-meta">
                    <h1 class="notes-title">${esc(note.title)}</h1>
                    <p class="notes-summary">${esc(note.summary)}</p>
                    ${note.youtube_url ? `<a class="notes-video-link" href="${esc(note.youtube_url)}" target="_blank" rel="noopener">▶ Watch on YouTube</a>` : ''}
                </div>
            </div>`;

        notesActions.innerHTML = `
            <button class="action-btn" id="copyMdBtn">📋 Copy as Markdown</button>
            <button class="action-btn" id="downloadMdBtn">⬇ Download .md</button>`;

        let html = '';

        if (note.topics && note.topics.length)
            html += section('📚', 'Topics', note.topics.length,
                note.topics.map(t => `
                    <div class="topic-card">
                        <div class="topic-card-title">${esc(t.title)}</div>
                        <div class="topic-card-content">${esc(t.content)}</div>
                        ${t.subtopics && t.subtopics.length ? `<div class="topic-subtopics">${t.subtopics.map(s => `<span class="subtopic-tag">${esc(s)}</span>`).join('')}</div>` : ''}
                    </div>`).join(''));

        if (note.definitions && note.definitions.length)
            html += section('📖', 'Definitions', note.definitions.length,
                `<div class="def-grid">${note.definitions.map(d => `
                    <div class="def-item">
                        <div class="def-term">${esc(d.term)}</div>
                        <div class="def-text">${esc(d.definition)}</div>
                    </div>`).join('')}</div>`);

        if (note.formulas && note.formulas.length)
            html += section('🧮', 'Formulas', note.formulas.length,
                note.formulas.map(f => `<div class="formula-item">${esc(f)}</div>`).join(''));

        if (note.examples && note.examples.length)
            html += section('💡', 'Examples', note.examples.length,
                note.examples.map(e => `<div class="example-item"><span class="item-bullet"></span><span>${esc(e)}</span></div>`).join(''));

        if (note.key_takeaways && note.key_takeaways.length)
            html += section('🎯', 'Key Takeaways', note.key_takeaways.length,
                note.key_takeaways.map(k => `<div class="takeaway-item"><span class="item-bullet"></span><span>${esc(k)}</span></div>`).join(''));

        if (note.interview_questions && note.interview_questions.length)
            html += section('💼', 'Interview Questions', note.interview_questions.length,
                note.interview_questions.map(q => `
                    <div class="qa-item">
                        <div class="qa-q"><span class="qa-label">Q:</span><span>${esc(q.question)}</span></div>
                        <div class="qa-a">${esc(q.suggested_answer)}</div>
                    </div>`).join(''));

        if (note.resources && note.resources.length)
            html += section('🔗', 'Resources', note.resources.length,
                note.resources.map(r => `
                    <div class="resource-item">
                        <span class="resource-icon">📄</span>
                        <div>
                            <div class="resource-title">${r.link ? `<a href="${esc(r.link)}" target="_blank" rel="noopener">${esc(r.title)}</a>` : esc(r.title)}</div>
                            ${r.link ? `<div class="resource-link">${esc(r.link)}</div>` : ''}
                        </div>
                    </div>`).join(''));

        notesContent.innerHTML = html;

        // Section collapse toggles
        notesContent.querySelectorAll('.section-header').forEach(hdr => {
            hdr.addEventListener('click', () => hdr.parentElement.classList.toggle('collapsed'));
        });

        // Export buttons
        $('#copyMdBtn').addEventListener('click', () => { copyMarkdown(note); });
        $('#downloadMdBtn').addEventListener('click', () => { downloadMarkdown(note); });
    }

    function section(icon, title, count, body) {
        return `<div class="section">
            <div class="section-header">
                <div class="section-header-left">
                    <span class="section-icon">${icon}</span>
                    <span class="section-title">${title}</span>
                    <span class="section-count">${count}</span>
                </div>
                <span class="section-toggle">▾</span>
            </div>
            <div class="section-body">${body}</div>
        </div>`;
    }

    // ── Export ───────────────────────────────────────────────
    function toMarkdown(n) {
        let md = `# ${n.title}\n\n${n.summary}\n`;
        if (n.topics?.length) { md += '\n## Topics\n'; n.topics.forEach(t => { md += `\n### ${t.title}\n${t.content}\n`; if (t.subtopics?.length) md += t.subtopics.map(s => `- ${s}`).join('\n') + '\n'; }); }
        if (n.definitions?.length) { md += '\n## Definitions\n'; n.definitions.forEach(d => { md += `- **${d.term}**: ${d.definition}\n`; }); }
        if (n.formulas?.length) { md += '\n## Formulas\n'; n.formulas.forEach(f => { md += `- \`${f}\`\n`; }); }
        if (n.examples?.length) { md += '\n## Examples\n'; n.examples.forEach(e => { md += `- ${e}\n`; }); }
        if (n.key_takeaways?.length) { md += '\n## Key Takeaways\n'; n.key_takeaways.forEach(k => { md += `- ${k}\n`; }); }
        if (n.interview_questions?.length) { md += '\n## Interview Questions\n'; n.interview_questions.forEach(q => { md += `\n**Q: ${q.question}**\n${q.suggested_answer}\n`; }); }
        if (n.resources?.length) { md += '\n## Resources\n'; n.resources.forEach(r => { md += `- [${r.title}](${r.link || '#'})\n`; }); }
        return md;
    }

    function copyMarkdown(n) {
        navigator.clipboard.writeText(toMarkdown(n)).then(() => toast('Copied to clipboard!', 'success')).catch(() => toast('Copy failed', 'error'));
    }

    function downloadMarkdown(n) {
        const blob = new Blob([toMarkdown(n)], { type: 'text/markdown' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${n.title.replace(/[^a-z0-9]/gi, '_').substring(0, 50)}.md`;
        a.click();
        URL.revokeObjectURL(a.href);
        toast('Download started', 'success');
    }

    // ── Health ──────────────────────────────────────────────
    async function checkHealth() {
        try {
            const h = await api.health();
            ollamaStatus.className = 'status-dot ' + (h.ollama_status === 'connected' ? 'connected' : 'disconnected');
            ollamaStatus.title = 'Ollama: ' + h.ollama_status;
        } catch { ollamaStatus.className = 'status-dot disconnected'; }
    }

    // ── Helpers ─────────────────────────────────────────────
    function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
    function fmtDate(iso) { try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return ''; } }
    function toast(msg, type = '') {
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = msg;
        toastContainer.appendChild(el);
        setTimeout(() => { el.classList.add('fade-out'); setTimeout(() => el.remove(), 300); }, 3000);
    }

    // ── Boot ────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', init);
})();

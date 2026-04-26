/**
 * NoteForge — Main Application Logic
 */

// ── DOM References ──────────────────────────────────────────────
const urlForm = document.getElementById('urlForm');
const urlInput = document.getElementById('urlInput');
const langSelect = document.getElementById('langSelect');
const submitBtn = document.getElementById('submitBtn');
const notesList = document.getElementById('notesList');
const emptyState = document.getElementById('emptyState');
const searchInput = document.getElementById('searchInput');
const newNoteBtn = document.getElementById('newNoteBtn');
const retryBtn = document.getElementById('retryBtn');
const ollamaStatus = document.getElementById('ollamaStatus');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');

// Views
const landingView = document.getElementById('landingView');
const loadingView = document.getElementById('loadingView');
const notesView = document.getElementById('notesView');
const errorView = document.getElementById('errorView');
const loadingStep = document.getElementById('loadingStep');
const progressBar = document.getElementById('progressBar');
const notesHeader = document.getElementById('notesHeader');
const notesActions = document.getElementById('notesActions');
const notesContent = document.getElementById('notesContent');
const errorMessage = document.getElementById('errorMessage');

// Batch modal
const batchModal = document.getElementById('batchModal');
const batchNoteBtn = document.getElementById('batchNoteBtn');
const batchModalClose = document.getElementById('batchModalClose');
const batchCancelBtn = document.getElementById('batchCancelBtn');
const batchSubmitBtn = document.getElementById('batchSubmitBtn');
const batchUrlsInput = document.getElementById('batchUrlsInput');
const batchLangSelect = document.getElementById('batchLangSelect');
const batchProgress = document.getElementById('batchProgress');
const batchStatus = document.getElementById('batchStatus');
const batchProgressBar = document.getElementById('batchProgressBar');
const batchResults = document.getElementById('batchResults');

// Quiz modal
const quizModal = document.getElementById('quizModal');
const quizModalClose = document.getElementById('quizModalClose');
const quizTitle = document.getElementById('quizTitle');
const quizBody = document.getElementById('quizBody');
const quizLoading = document.getElementById('quizLoading');

const toastContainer = document.getElementById('toastContainer');

// ── State ───────────────────────────────────────────────────────
let currentNote = null;
let activeNoteId = null;
let allNotes = [];
let progressInterval = null;

// ── View Management ─────────────────────────────────────────────
function showView(name) {
    [landingView, loadingView, notesView, errorView].forEach(v => v.classList.remove('active'));
    const map = { landing: landingView, loading: loadingView, notes: notesView, error: errorView };
    if (map[name]) map[name].classList.add('active');
}

// ── Toast Notifications ─────────────────────────────────────────
function toast(message, type = 'info') {
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.textContent = message;
    toastContainer.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
        el.classList.remove('show');
        setTimeout(() => el.remove(), 300);
    }, 3500);
}

// ── Progress Animation ──────────────────────────────────────────
function animateProgress() {
    let pct = 0;
    const steps = [
        { at: 10, text: 'Extracting transcript from YouTube...' },
        { at: 30, text: 'Sending transcript to AI model...' },
        { at: 50, text: 'Generating structured notes...' },
        { at: 70, text: 'Formatting and validating output...' },
        { at: 85, text: 'Saving notes to database...' },
    ];
    progressInterval = setInterval(() => {
        if (pct < 90) pct += Math.random() * 3;
        progressBar.style.width = pct + '%';
        const step = [...steps].reverse().find(s => pct >= s.at);
        if (step) loadingStep.textContent = step.text;
    }, 600);
}

function resetProgress() {
    clearInterval(progressInterval);
    progressInterval = null;
    progressBar.style.width = '0%';
    loadingStep.textContent = 'Extracting transcript from YouTube...';
}

// ── Error Display ───────────────────────────────────────────────
function showError(msg) {
    errorMessage.textContent = msg;
    showView('error');
}

// ── Date Formatting ─────────────────────────────────────────────
function formatDate(iso) {
    try {
        const d = new Date(iso);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch { return ''; }
}

// ── Sidebar: Load Notes ─────────────────────────────────────────
async function loadNotes() {
    try {
        allNotes = await api.listNotes();
        renderNotesList(allNotes);
    } catch (err) {
        console.error('Failed to load notes list:', err);
    }
}

function renderNotesList(notes) {
    notesList.innerHTML = '';
    if (!notes || notes.length === 0) {
        notesList.appendChild(emptyState);
        emptyState.style.display = '';
        return;
    }
    emptyState.style.display = 'none';
    notes.forEach(n => {
        const item = document.createElement('div');
        item.className = 'note-item' + (n.id === activeNoteId ? ' active' : '');
        item.innerHTML = `
            <div class="note-item-info">
                <div class="note-item-title">${escapeHtml(n.title || 'Untitled Lecture')}</div>
                <div class="note-item-date">${formatDate(n.created_at)}</div>
            </div>
            <button class="note-item-delete" title="Delete note">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                    <path d="M3 6h18"/><path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                    <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
                </svg>
            </button>`;
        item.querySelector('.note-item-info').addEventListener('click', () => openNote(n.id));
        item.querySelector('.note-item-delete').addEventListener('click', e => { e.stopPropagation(); deleteNote(n.id); });
        notesList.appendChild(item);
    });
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// ── Sidebar: Search ─────────────────────────────────────────────
searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) return renderNotesList(allNotes);
    renderNotesList(allNotes.filter(n => (n.title || '').toLowerCase().includes(q)));
});

// ── Open / Delete Note ──────────────────────────────────────────
async function openNote(id) {
    try {
        const note = await api.getNote(id);
        currentNote = note;
        activeNoteId = id;
        renderNote(note);
        showView('notes');
        renderNotesList(allNotes);
        closeMobileSidebar();
    } catch (err) {
        toast('Failed to load note', 'error');
    }
}

async function deleteNote(id) {
    if (!confirm('Delete this note?')) return;
    try {
        await api.deleteNote(id);
        toast('Note deleted', 'success');
        if (activeNoteId === id) { activeNoteId = null; currentNote = null; showView('landing'); }
        await loadNotes();
    } catch (err) {
        toast('Failed to delete note', 'error');
    }
}

// ── Render Note ─────────────────────────────────────────────────
function renderNote(note) {
    const thumbUrl = note.video_id ? `https://img.youtube.com/vi/${note.video_id}/mqdefault.jpg` : '';
    notesHeader.innerHTML = `
        <div class="notes-header-inner">
            ${thumbUrl ? `<img class="notes-thumb" src="${thumbUrl}" alt="Video thumbnail">` : ''}
            <div class="notes-meta">
                <h1 class="notes-title">${escapeHtml(note.title)}</h1>
                <p class="notes-summary">${escapeHtml(note.summary)}</p>
                ${note.youtube_url ? `<a class="notes-video-link" href="${escapeHtml(note.youtube_url)}" target="_blank" rel="noopener">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                    Watch on YouTube</a>` : ''}
            </div>
        </div>`;

    notesActions.innerHTML = `
        <button class="action-btn" id="quizBtn" title="Generate Quiz"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Quiz Me</button>
        <button class="action-btn" id="pdfBtn" title="Export PDF"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg> Export PDF</button>`;

    document.getElementById('quizBtn').addEventListener('click', () => startQuiz(note.id));
    document.getElementById('pdfBtn').addEventListener('click', () => exportPdf(note));

    let html = '';

    // Topics
    if (note.topics && note.topics.length) {
        html += '<div class="notes-section"><h2 class="section-title">Topics</h2>';
        note.topics.forEach(t => {
            const title = typeof t === 'string' ? t : (t.title || '');
            const content = typeof t === 'string' ? '' : (t.content || '');
            const subs = (typeof t === 'object' && t.subtopics) ? t.subtopics : [];
            html += `<div class="topic-card"><h3 class="topic-title">${escapeHtml(title)}</h3>`;
            if (content) html += `<p class="topic-content">${escapeHtml(content)}</p>`;
            if (subs.length) { html += '<ul class="topic-subs">'; subs.forEach(s => html += `<li>${escapeHtml(String(s))}</li>`); html += '</ul>'; }
            html += '</div>';
        });
        html += '</div>';
    }

    // Definitions
    if (note.definitions && note.definitions.length) {
        html += '<div class="notes-section"><h2 class="section-title">Definitions</h2><div class="def-grid">';
        note.definitions.forEach(d => {
            const term = typeof d === 'string' ? d : (d.term || '');
            const def = typeof d === 'string' ? '' : (d.definition || '');
            html += `<div class="def-card"><span class="def-term">${escapeHtml(term)}</span><span class="def-text">${escapeHtml(def)}</span></div>`;
        });
        html += '</div></div>';
    }

    // Formulas
    if (note.formulas && note.formulas.length) {
        html += '<div class="notes-section"><h2 class="section-title">Formulas</h2>';
        note.formulas.forEach(f => html += `<div class="formula-card"><code>${escapeHtml(String(f))}</code></div>`);
        html += '</div>';
    }

    // Examples
    if (note.examples && note.examples.length) {
        html += '<div class="notes-section"><h2 class="section-title">Examples</h2><ul class="examples-list">';
        note.examples.forEach(ex => html += `<li>${escapeHtml(String(ex))}</li>`);
        html += '</ul></div>';
    }

    // Key Takeaways
    if (note.key_takeaways && note.key_takeaways.length) {
        html += '<div class="notes-section"><h2 class="section-title">Key Takeaways</h2><ul class="takeaways-list">';
        note.key_takeaways.forEach(kt => html += `<li>${escapeHtml(String(kt))}</li>`);
        html += '</ul></div>';
    }

    // Interview Questions
    if (note.interview_questions && note.interview_questions.length) {
        html += '<div class="notes-section"><h2 class="section-title">Interview Questions</h2>';
        note.interview_questions.forEach(iq => {
            const q = typeof iq === 'string' ? iq : (iq.question || '');
            const a = typeof iq === 'string' ? '' : (iq.suggested_answer || '');
            html += `<div class="iq-card"><div class="iq-q">${escapeHtml(q)}</div>`;
            if (a) html += `<div class="iq-a">${escapeHtml(a)}</div>`;
            html += '</div>';
        });
        html += '</div>';
    }

    // Resources
    if (note.resources && note.resources.length) {
        html += '<div class="notes-section"><h2 class="section-title">Resources</h2><ul class="resources-list">';
        note.resources.forEach(r => {
            const title = typeof r === 'string' ? r : (r.title || '');
            const link = typeof r === 'object' ? r.link : null;
            html += link ? `<li><a href="${escapeHtml(link)}" target="_blank" rel="noopener">${escapeHtml(title)}</a></li>` : `<li>${escapeHtml(title)}</li>`;
        });
        html += '</ul></div>';
    }

    notesContent.innerHTML = html;
}

// ── Generate Notes (Form Submit) ────────────────────────────────
async function onSubmit(e) {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;
    const lang = langSelect.value || null;

    showView('loading');
    submitBtn.disabled = true;
    animateProgress();

    try {
        const note = await api.generateNotes(url, lang);
        if (!note || !note.id || !note.title || !note.summary) {
            throw new Error('Backend returned incomplete note data. Check FastAPI logs.');
        }
        currentNote = note;
        activeNoteId = note.id;
        await loadNotes();
        renderNote(note);
        showView('notes');
        toast('Notes generated successfully!', 'success');
    } catch (err) {
        console.error('Generate notes failed:', err);
        showError(err.message || 'Failed to generate notes');
        toast(err.message || 'Failed to generate notes', 'error');
    } finally {
        submitBtn.disabled = false;
        resetProgress();
    }
}

// ── Quiz ────────────────────────────────────────────────────────
async function startQuiz(noteId) {
    quizModal.classList.add('active');
    quizLoading.style.display = '';
    quizBody.querySelectorAll('.quiz-question-card, .quiz-score').forEach(el => el.remove());
    quizTitle.textContent = 'Quiz Mode';

    try {
        const data = await api.generateQuiz(noteId);
        quizLoading.style.display = 'none';
        quizTitle.textContent = data.note_title ? `Quiz: ${data.note_title}` : 'Quiz Mode';
        renderQuiz(data.questions || []);
    } catch (err) {
        quizLoading.style.display = 'none';
        quizBody.innerHTML += `<p style="color:var(--error);text-align:center;padding:20px;">${escapeHtml(err.message)}</p>`;
        toast('Quiz generation failed', 'error');
    }
}

function renderQuiz(questions) {
    if (!questions.length) {
        quizBody.innerHTML += '<p style="text-align:center;padding:20px;color:var(--text-muted);">No questions generated.</p>';
        return;
    }
    let answered = 0, correct = 0;

    questions.forEach((q, qi) => {
        const card = document.createElement('div');
        card.className = 'quiz-question-card';
        let optHtml = '';
        (q.options || []).forEach((opt, oi) => {
            optHtml += `<button class="quiz-option" data-qi="${qi}" data-oi="${oi}">${escapeHtml(String(opt))}</button>`;
        });
        card.innerHTML = `<div class="quiz-q-num">Q${qi + 1}</div><div class="quiz-q-text">${escapeHtml(q.question)}</div><div class="quiz-options">${optHtml}</div><div class="quiz-explanation" style="display:none;">${escapeHtml(q.explanation || '')}</div>`;
        quizBody.appendChild(card);

        card.querySelectorAll('.quiz-option').forEach(btn => {
            btn.addEventListener('click', () => {
                if (card.classList.contains('answered')) return;
                card.classList.add('answered');
                answered++;
                const selected = parseInt(btn.dataset.oi);
                const isCorrect = selected === q.correct_index;
                if (isCorrect) correct++;
                btn.classList.add(isCorrect ? 'correct' : 'wrong');
                const correctBtn = card.querySelector(`.quiz-option[data-oi="${q.correct_index}"]`);
                if (correctBtn && !isCorrect) correctBtn.classList.add('correct');
                card.querySelector('.quiz-explanation').style.display = '';

                if (answered === questions.length) {
                    const score = document.createElement('div');
                    score.className = 'quiz-score';
                    score.innerHTML = `<h3>Score: ${correct}/${questions.length}</h3><p>${correct === questions.length ? 'Perfect!' : correct >= questions.length * 0.7 ? 'Great job!' : 'Keep studying!'}</p>`;
                    quizBody.appendChild(score);
                }
            });
        });
    });
}

// ── PDF Export ───────────────────────────────────────────────────
function exportPdf(note) {
    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        let y = 20;
        const margin = 15;
        const pageW = doc.internal.pageSize.getWidth() - margin * 2;

        function addText(text, size, bold, color) {
            doc.setFontSize(size);
            if (bold) doc.setFont(undefined, 'bold'); else doc.setFont(undefined, 'normal');
            if (color) doc.setTextColor(...color); else doc.setTextColor(33, 33, 33);
            const lines = doc.splitTextToSize(text, pageW);
            lines.forEach(line => {
                if (y > 270) { doc.addPage(); y = 20; }
                doc.text(line, margin, y);
                y += size * 0.5;
            });
            y += 4;
        }

        addText(note.title || 'Untitled', 18, true);
        addText(note.summary || '', 10, false, [100, 100, 100]);
        y += 4;

        if (note.topics && note.topics.length) {
            addText('Topics', 14, true, [108, 92, 231]);
            note.topics.forEach(t => {
                addText(typeof t === 'string' ? t : (t.title || ''), 11, true);
                const c = typeof t === 'string' ? '' : (t.content || '');
                if (c) addText(c, 10, false, [80, 80, 80]);
            });
            y += 2;
        }

        if (note.key_takeaways && note.key_takeaways.length) {
            addText('Key Takeaways', 14, true, [108, 92, 231]);
            note.key_takeaways.forEach(kt => addText('• ' + String(kt), 10, false));
        }

        doc.save(`${(note.title || 'notes').replace(/[^a-zA-Z0-9]/g, '_')}.pdf`);
        toast('PDF exported!', 'success');
    } catch (err) {
        console.error('PDF export failed:', err);
        toast('PDF export failed', 'error');
    }
}

// ── Batch Processing ────────────────────────────────────────────
async function onBatchSubmit() {
    const raw = batchUrlsInput.value.trim();
    if (!raw) return;
    const urls = raw.split('\n').map(u => u.trim()).filter(u => u);
    if (!urls.length) return;
    if (urls.length > 10) { toast('Maximum 10 URLs allowed', 'error'); return; }

    const lang = batchLangSelect.value || null;
    batchSubmitBtn.disabled = true;
    batchProgress.style.display = '';
    batchStatus.textContent = `Processing ${urls.length} URLs...`;
    batchProgressBar.style.width = '0%';
    batchResults.innerHTML = '';

    try {
        const data = await api.batchGenerate(urls, lang);
        batchProgressBar.style.width = '100%';
        batchStatus.textContent = `Done: ${data.succeeded} succeeded, ${data.failed} failed`;

        (data.results || []).forEach(r => {
            const div = document.createElement('div');
            div.className = `batch-result-item ${r.status}`;
            div.textContent = r.status === 'success'
                ? `✓ ${r.note?.title || r.youtube_url}`
                : `✗ ${r.youtube_url}: ${r.error || 'Failed'}`;
            batchResults.appendChild(div);
        });

        await loadNotes();
        toast(`Batch complete: ${data.succeeded}/${data.total} succeeded`, data.failed ? 'warning' : 'success');
    } catch (err) {
        batchStatus.textContent = 'Batch failed';
        toast(err.message || 'Batch processing failed', 'error');
    } finally {
        batchSubmitBtn.disabled = false;
    }
}

// ── Mobile Sidebar ──────────────────────────────────────────────
function toggleMobileSidebar() {
    sidebar.classList.toggle('open');
    sidebarOverlay.classList.toggle('active');
}
function closeMobileSidebar() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('active');
}

// ── Health Check ────────────────────────────────────────────────
async function checkHealth() {
    try {
        const h = await api.health();
        ollamaStatus.className = 'status-dot ' + (h.ollama_status === 'connected' ? 'connected' : 'disconnected');
    } catch {
        ollamaStatus.className = 'status-dot disconnected';
    }
}

// ── Event Listeners ─────────────────────────────────────────────
urlForm.addEventListener('submit', onSubmit);
newNoteBtn.addEventListener('click', () => { showView('landing'); urlInput.focus(); closeMobileSidebar(); });
retryBtn.addEventListener('click', () => showView('landing'));
mobileMenuBtn.addEventListener('click', toggleMobileSidebar);
sidebarOverlay.addEventListener('click', closeMobileSidebar);

// Batch modal
batchNoteBtn.addEventListener('click', () => { batchModal.classList.add('active'); batchProgress.style.display = 'none'; batchResults.innerHTML = ''; });
batchModalClose.addEventListener('click', () => batchModal.classList.remove('active'));
batchCancelBtn.addEventListener('click', () => batchModal.classList.remove('active'));
batchSubmitBtn.addEventListener('click', onBatchSubmit);

// Quiz modal
quizModalClose.addEventListener('click', () => quizModal.classList.remove('active'));

// Close modals on overlay click
[batchModal, quizModal].forEach(m => m.addEventListener('click', e => { if (e.target === m) m.classList.remove('active'); }));

// ── Init ────────────────────────────────────────────────────────
(async function init() {
    await loadNotes();
    checkHealth();
    setInterval(checkHealth, 30000);
})();
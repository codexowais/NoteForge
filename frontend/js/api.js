/**
 * NoteForge API Client
 *
 * All HTTP calls to the FastAPI backend.
 */

const API_BASE = '/api/v1';

const api = {
    /**
     * Generate notes from a YouTube URL.
     * POST /api/v1/generate-notes
     */
    async generateNotes(youtubeUrl) {
        const res = await fetch(`${API_BASE}/generate-notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ youtube_url: youtubeUrl }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Server error (${res.status})`);
        }
        return res.json();
    },

    /**
     * List all saved notes (metadata only).
     * GET /api/v1/notes
     */
    async listNotes() {
        const res = await fetch(`${API_BASE}/notes`);
        if (!res.ok) throw new Error('Failed to load notes');
        return res.json();
    },

    /**
     * Get a single note by ID (full data).
     * GET /api/v1/notes/:id
     */
    async getNote(id) {
        const res = await fetch(`${API_BASE}/notes/${id}`);
        if (!res.ok) throw new Error('Note not found');
        return res.json();
    },

    /**
     * Delete a note by ID.
     * DELETE /api/v1/notes/:id
     */
    async deleteNote(id) {
        const res = await fetch(`${API_BASE}/notes/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to delete note');
        return res.json();
    },

    /**
     * Health check.
     * GET /api/v1/health
     */
    async health() {
        const res = await fetch(`${API_BASE}/health`);
        if (!res.ok) throw new Error('Health check failed');
        return res.json();
    },
};

/**
 * API service layer — all backend calls in one place.
 *
 * In development, Vite proxies /api → http://localhost:8000.
 * In production, set VITE_API_URL to the real backend URL.
 */

const BASE = import.meta.env.VITE_API_URL || '/api';

async function request(path, options = {}) {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// ─── Upload ──────────────────────────────────────────────────

export async function uploadDocument(file, studentId = '', courseId = '') {
  const form = new FormData();
  form.append('file', file);

  const params = new URLSearchParams();
  if (studentId) params.set('student_id', studentId);
  if (courseId)  params.set('course_id', courseId);

  const qs = params.toString() ? `?${params}` : '';
  const res = await fetch(`${BASE}/upload${qs}`, {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed (${res.status})`);
  }
  return res.json();
}

// ─── Documents ───────────────────────────────────────────────

export async function listDocuments() {
  return request('/documents');
}

export async function getDocumentStatus(docId) {
  return request(`/documents/${docId}/status`);
}

// ─── Q&A ─────────────────────────────────────────────────────

export async function askQuestion(payload) {
  return request('/ask', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ─── Quiz ────────────────────────────────────────────────────

export async function generateQuiz(payload) {
  return request('/quiz', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ─── Summarize ───────────────────────────────────────────────

export async function summarizeDocument(payload) {
  return request('/summarize', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ─── Mind Map ────────────────────────────────────────────────

export async function generateMindMap(payload) {
  return request('/mindmap', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

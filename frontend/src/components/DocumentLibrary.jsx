import React, { useState, useEffect, useCallback } from 'react';
import { listDocuments } from '../services/api';

function fileIcon(filename) {
  if (!filename) return '📄';
  const ext = filename.slice(filename.lastIndexOf('.')).toLowerCase();
  if (ext === '.pdf') return '📄';
  if (ext === '.pptx') return '📊';
  if (ext === '.md') return '📝';
  return '📝';
}

function statusBadge(status) {
  switch (status) {
    case 'processed': return <span className="badge badge-success">● Ready</span>;
    case 'processing': return <span className="badge badge-warning">◌ Processing</span>;
    case 'failed': return <span className="badge badge-error">✕ Failed</span>;
    default: return <span className="badge badge-info">◌ Uploaded</span>;
  }
}

function timeAgo(ts) {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function DocumentLibrary({ onSelectDoc, refreshKey }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDocs = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listDocuments();
      setDocuments(Array.isArray(data) ? data : data.documents || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
    const timer = setInterval(() => {
      fetchDocs();
    }, 3000);
    return () => clearInterval(timer);
  }, [fetchDocs, refreshKey]);

  if (loading) {
    return (
      <div className="loading-overlay">
        <div className="spinner spinner-lg" />
        <span>Loading documents…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">⚠️</div>
        <div className="empty-state-title">Could not load documents</div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 8 }}>{error}</p>
        <button className="btn btn-secondary" style={{ marginTop: 16 }} onClick={fetchDocs}>
          Retry
        </button>
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="empty-state animate-fade-in">
        <div className="empty-state-icon">📚</div>
        <div className="empty-state-title">No documents yet</div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 4 }}>
          Upload your first document to get started
        </p>
      </div>
    );
  }

  return (
    <div className="animate-slide-up">
      <div className="doc-grid">
        {documents.map((doc) => (
          <div
            key={doc.doc_id}
            id={`doc-${doc.doc_id}`}
            className="card doc-card"
            onClick={() => onSelectDoc?.(doc)}
          >
            <div className="doc-card-icon">{fileIcon(doc.filename)}</div>
            <div className="doc-card-title" title={doc.filename}>
              {doc.filename || doc.doc_id}
            </div>
            <div style={{ marginTop: 6 }}>{statusBadge(doc.status)}</div>
            <div className="doc-card-meta">
              <span>{timeAgo(doc.uploaded_at)}</span>
              {doc.file_type && <span>• {doc.file_type.toUpperCase().replace('.','')}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { getDocumentStatus } from '../services/api';

export default function DocumentDetail({ doc: initialDoc, onAction, onBack }) {
  const [doc, setDoc] = useState(initialDoc);

  useEffect(() => {
    let active = true;
    async function refreshStatus() {
      try {
        const latest = await getDocumentStatus(initialDoc.doc_id);
        if (active && latest) {
          setDoc(latest);
        }
      } catch (err) {
        // Keep initialDoc if fetch fails
      }
    }
    refreshStatus();

    const interval = setInterval(() => {
      if (doc?.status !== 'processed' && doc?.status !== 'failed') {
        refreshStatus();
      }
    }, 3000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [initialDoc.doc_id, doc?.status]);

  const actions = [
    {
      key: 'ask',
      icon: '💬',
      label: 'Ask Questions',
      desc: 'Chat with your document using AI',
      color: 'var(--indigo)',
    },
    {
      key: 'quiz',
      icon: '🧠',
      label: 'Generate Quiz',
      desc: 'Test your knowledge with MCQs',
      color: 'var(--emerald)',
    },
    {
      key: 'summarize',
      icon: '📋',
      label: 'Summarize',
      desc: 'Get a concise summary with key points',
      color: 'var(--cyan)',
    },
    {
      key: 'mindmap',
      icon: '🗺️',
      label: 'Mind Map',
      desc: 'Visualize concepts as a mind map',
      color: 'var(--amber)',
    },
  ];

  const filename = doc.original_filename || doc.filename || doc.doc_id;

  return (
    <div className="animate-slide-up">
      <button className="back-btn" onClick={onBack}>
        ← Back to Documents
      </button>

      {/* Document Info Card */}
      <div className="card" style={{ padding: 24, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: '2.5rem' }}>
            {doc.file_type === '.pdf' ? '📄' : doc.file_type === '.pptx' ? '📊' : '📝'}
          </span>
          <div style={{ flex: 1 }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
              {filename}
            </h3>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: 4, display: 'flex', gap: 16, alignItems: 'center' }}>
              <span>ID: {doc.doc_id.slice(0, 8)}…</span>
              {doc.file_type && <span>{doc.file_type.toUpperCase().replace('.','')}</span>}
              <span className={`badge badge-${doc.status === 'processed' ? 'success' : doc.status === 'failed' ? 'error' : 'warning'}`}>
                {doc.status === 'processed' ? '● Ready' : doc.status === 'failed' ? '✕ Failed' : '◌ Processing / Uploaded'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <h3 style={{ fontSize: '1rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
        Study Tools
      </h3>
      <div className="action-grid">
        {actions.map(a => (
          <div
            key={a.key}
            id={`action-${a.key}`}
            className="card action-card"
            onClick={() => onAction?.(a.key)}
          >
            <span className="action-icon">{a.icon}</span>
            <div className="action-label">{a.label}</div>
            <div className="action-desc">{a.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

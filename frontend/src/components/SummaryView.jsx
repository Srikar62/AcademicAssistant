import React, { useState } from 'react';
import { summarizeDocument } from '../services/api';
import { useToast } from './Toast';

export default function SummaryView({ doc, onBack }) {
  const toast = useToast();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [length, setLength] = useState('medium');
  const [topic, setTopic] = useState('');

  const handleGenerate = async () => {
    setLoading(true);
    setSummary(null);

    try {
      const result = await summarizeDocument({
        doc_id: doc?.doc_id,
        max_length: length,
        topic: topic || undefined,
      });
      setSummary(result);
    } catch (err) {
      toast.error(`Summarization failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-slide-up">
      <button className="back-btn" onClick={onBack}>← Back to Document</button>

      {/* Config */}
      {!summary && !loading && (
        <div className="card" style={{ padding: 24, marginBottom: 20 }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 16 }}>📋 Generate Summary</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                Length
              </label>
              <select
                className="input"
                style={{ width: 130 }}
                value={length}
                onChange={(e) => setLength(e.target.value)}
              >
                <option value="brief">Brief</option>
                <option value="medium">Medium</option>
                <option value="detailed">Detailed</option>
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                Focus Topic (optional)
              </label>
              <input
                className="input"
                placeholder="e.g., deep learning"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </div>
            <button className="btn btn-primary" onClick={handleGenerate}>
              Summarize
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner spinner-lg" />
          <span>Generating summary…</span>
        </div>
      )}

      {/* Summary Result */}
      {summary && (
        <div className="card" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>📋 Summary</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => setSummary(null)}>
              New Summary
            </button>
          </div>

          {/* Source Info */}
          {summary.source_documents?.length > 0 && (
            <div style={{ marginBottom: 16, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {summary.source_documents.map((s, i) => (
                <span key={i} className="badge badge-accent">{s}</span>
              ))}
              <span className="badge badge-info">{summary.chunks_used} chunks</span>
            </div>
          )}

          {/* Summary Text */}
          <div className="summary-content">
            {summary.summary.split('\n').map((p, i) =>
              p.trim() ? <p key={i}>{p}</p> : null
            )}
          </div>

          {/* Key Points */}
          {summary.key_points?.length > 0 && (
            <div className="key-points">
              <h3>Key Points</h3>
              {summary.key_points.map((kp, i) => (
                <div key={i} className="key-point">
                  <span className="key-point-bullet">▸</span>
                  <span>{kp}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

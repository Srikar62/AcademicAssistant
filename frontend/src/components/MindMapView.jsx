import React, { useState, useEffect, useRef } from 'react';
import { generateMindMap } from '../services/api';
import { useToast } from './Toast';
import mermaid from 'mermaid';

// Initialize Mermaid with dark theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#7c3aed',
    primaryTextColor: '#f0f0f8',
    primaryBorderColor: '#5b21b6',
    lineColor: '#6366f1',
    secondaryColor: '#141428',
    tertiaryColor: '#0d0d1a',
  },
  mindmap: {
    padding: 20,
  },
});

export default function MindMapView({ doc, onBack }) {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [topic, setTopic] = useState('');
  const containerRef = useRef(null);

  const handleGenerate = async () => {
    setLoading(true);
    setData(null);

    try {
      const result = await generateMindMap({
        doc_id: doc?.doc_id,
        topic: topic || undefined,
      });
      setData(result);
    } catch (err) {
      toast.error(`Mind map generation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Render Mermaid when data changes
  useEffect(() => {
    if (!data?.mermaid_syntax || !containerRef.current) return;

    const render = async () => {
      try {
        containerRef.current.innerHTML = '';
        const id = `mermaid-${Date.now()}`;
        const { svg } = await mermaid.render(id, data.mermaid_syntax);
        containerRef.current.innerHTML = svg;
      } catch (err) {
        console.error('Mermaid render error:', err);
        containerRef.current.innerHTML = `<pre style="color:var(--text-muted);font-size:0.85rem;white-space:pre-wrap">${data.mermaid_syntax}</pre>`;
      }
    };

    render();
  }, [data]);

  return (
    <div className="animate-slide-up">
      <button className="back-btn" onClick={onBack}>← Back to Document</button>

      {/* Config */}
      {!data && !loading && (
        <div className="card" style={{ padding: 24, marginBottom: 20 }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: 16 }}>🗺️ Generate Mind Map</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>
                Focus Topic (optional)
              </label>
              <input
                className="input"
                placeholder="e.g., machine learning algorithms"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              />
            </div>
            <button className="btn btn-primary" onClick={handleGenerate}>
              Generate Mind Map
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner spinner-lg" />
          <span>Generating mind map…</span>
        </div>
      )}

      {/* Mind Map */}
      {data && (
        <div className="card" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>🗺️ Mind Map</h3>
            <button className="btn btn-secondary btn-sm" onClick={() => setData(null)}>
              Generate New
            </button>
          </div>

          {/* Source Info */}
          {data.source_documents?.length > 0 && (
            <div style={{ marginBottom: 16, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {data.source_documents.map((s, i) => (
                <span key={i} className="badge badge-accent">{s}</span>
              ))}
              <span className="badge badge-info">{data.chunks_used} chunks</span>
            </div>
          )}

          {/* Rendered Mind Map */}
          <div className="mindmap-container" ref={containerRef}>
            <div className="spinner spinner-lg" />
          </div>
        </div>
      )}
    </div>
  );
}

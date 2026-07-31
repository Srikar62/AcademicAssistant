import React, { useState, useRef, useCallback } from 'react';
import { uploadDocument } from '../services/api';
import { useToast } from './Toast';

const ALLOWED = ['.pdf', '.pptx', '.txt', '.md'];

function fileTypeIcon(name) {
  const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
  if (ext === '.pdf') return '📄';
  if (ext === '.pptx') return '📊';
  return '📝';
}

export default function Upload({ onUploaded }) {
  const toast = useToast();
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [recent, setRecent] = useState([]);

  const handleFiles = useCallback(async (files) => {
    const valid = Array.from(files).filter(f => {
      const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase();
      return ALLOWED.includes(ext);
    });

    if (valid.length === 0) {
      toast.error('Unsupported file type. Use PDF, PPTX, TXT, or MD.');
      return;
    }

    setUploading(true);
    setProgress(10);

    for (const file of valid) {
      try {
        setProgress(30);
        const result = await uploadDocument(file);
        setProgress(100);
        setRecent(prev => [{ name: file.name, docId: result.doc_id, status: 'uploaded' }, ...prev]);
        toast.success(`Uploaded "${file.name}" successfully!`);
        if (onUploaded) onUploaded(result);
      } catch (err) {
        toast.error(`Failed to upload "${file.name}": ${err.message}`);
      }
    }

    setUploading(false);
    setTimeout(() => setProgress(0), 800);
  }, [toast, onUploaded]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="animate-slide-up">
      {/* Drop Zone */}
      <div
        id="upload-zone"
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <span className="upload-icon">📁</span>
        <div className="upload-title">
          {uploading ? 'Uploading…' : 'Drop files here or click to browse'}
        </div>
        <div className="upload-subtitle">
          Upload lecture slides, PDFs, or notes for AI-powered study tools
        </div>
        <div className="upload-formats">
          <span className="badge badge-accent">PDF</span>
          <span className="badge badge-accent">PPTX</span>
          <span className="badge badge-accent">TXT</span>
          <span className="badge badge-accent">MD</span>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.pptx,.txt,.md"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(e.target.files)}
        />
        {progress > 0 && (
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        )}
      </div>

      {/* Recent Uploads */}
      {recent.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: '0.95rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
            Recent Uploads
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recent.map((r, i) => (
              <div key={i} className="card" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
                <span>{fileTypeIcon(r.name)}</span>
                <span style={{ flex: 1, fontSize: '0.875rem' }}>{r.name}</span>
                <span className="badge badge-success">✓ Uploaded</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

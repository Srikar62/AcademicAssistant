import React, { useState, useRef, useEffect } from 'react';
import { askQuestion } from '../services/api';
import { useToast } from './Toast';

export default function QAChat({ doc, onBack }) {
  const toast = useToast();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: question }]);
    setLoading(true);

    try {
      const result = await askQuestion({
        question,
        doc_id: doc?.doc_id,
      });

      setMessages(prev => [...prev, {
        role: 'assistant',
        text: result.answer,
        citations: result.citations || [],
      }]);
    } catch (err) {
      toast.error(`Q&A failed: ${err.message}`);
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `Sorry, I encountered an error: ${err.message}`,
        citations: [],
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="animate-slide-up">
      <button className="back-btn" onClick={onBack}>← Back to Document</button>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {/* Header */}
        <div className="card-header">
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>💬 Ask about your document</h3>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2 }}>
              {doc?.filename || 'All documents'}
            </p>
          </div>
        </div>

        {/* Messages */}
        <div style={{ padding: '0 20px' }}>
          <div className="chat-container">
            <div className="chat-messages">
              {messages.length === 0 && (
                <div className="empty-state" style={{ padding: '40px 0' }}>
                  <div className="empty-state-icon">💬</div>
                  <div className="empty-state-title">Ask a question</div>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 4 }}>
                    Ask anything about your study materials
                  </p>
                </div>
              )}

              {messages.map((msg, i) => (
                <div key={i} className={`chat-bubble ${msg.role}`}>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
                  {msg.citations?.length > 0 && (
                    <div className="citations">
                      {msg.citations.map((c, j) => (
                        <span key={j} className="badge badge-accent" title={c.original_filename}>
                          {c.source_label}
                          {c.relevance_score ? ` (${Math.round(c.relevance_score * 100)}%)` : ''}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="chat-bubble assistant" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div className="spinner" />
                  <span style={{ color: 'var(--text-muted)' }}>Thinking…</span>
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="chat-input-area">
              <input
                id="chat-input"
                className="input"
                type="text"
                placeholder="Ask a question about your document…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
              <button
                id="chat-send"
                className="btn btn-primary"
                onClick={handleSend}
                disabled={!input.trim() || loading}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

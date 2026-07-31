import React, { useState, useCallback } from 'react';
import Upload from './components/Upload';
import DocumentLibrary from './components/DocumentLibrary';
import DocumentDetail from './components/DocumentDetail';
import QAChat from './components/QAChat';
import QuizView from './components/QuizView';
import SummaryView from './components/SummaryView';
import MindMapView from './components/MindMapView';

/**
 * Views:
 *   upload    — drag-and-drop file upload
 *   library   — document grid
 *   detail    — single doc with action cards
 *   ask       — Q&A chat
 *   quiz      — quiz generation & interaction
 *   summarize — summary generation
 *   mindmap   — mind map generation & rendering
 */

const NAV_ITEMS = [
  { key: 'upload',  icon: '📤', label: 'Upload' },
  { key: 'library', icon: '📚', label: 'Documents' },
];

export default function App() {
  const [view, setView] = useState('upload');
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const navigate = useCallback((v, doc = null) => {
    setView(v);
    if (doc) setSelectedDoc(doc);
    setSidebarOpen(false);
  }, []);

  const handleUploaded = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  const handleSelectDoc = useCallback((doc) => {
    setSelectedDoc(doc);
    setView('detail');
  }, []);

  const handleAction = useCallback((action) => {
    setView(action);
  }, []);

  const goBackToDetail = useCallback(() => {
    setView('detail');
  }, []);

  const goBackToLibrary = useCallback(() => {
    setView('library');
    setSelectedDoc(null);
  }, []);

  // Page title + subtitle
  const pageInfo = {
    upload:    { title: 'Upload Documents', sub: 'Add lecture slides, PDFs, or notes' },
    library:   { title: 'Document Library', sub: 'Browse and manage your uploaded files' },
    detail:    { title: selectedDoc?.filename || 'Document', sub: 'Choose a study tool' },
    ask:       { title: 'Q&A Chat', sub: 'Ask questions about your documents' },
    quiz:      { title: 'Quiz', sub: 'Test your knowledge' },
    summarize: { title: 'Summary', sub: 'Generate a concise summary' },
    mindmap:   { title: 'Mind Map', sub: 'Visualize concepts' },
  };

  const info = pageInfo[view] || pageInfo.upload;

  return (
    <div className="app-layout">
      {/* Mobile menu button */}
      <button
        className="mobile-menu-btn"
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        ☰
      </button>

      {/* ─── Sidebar ─────────────────────────────────────── */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <h1>Academic Assistant</h1>
          <p>AI-Powered Study Tools</p>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.key}
              id={`nav-${item.key}`}
              className={`nav-item ${view === item.key ? 'active' : ''}`}
              onClick={() => navigate(item.key)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}

          {/* Show current doc in sidebar when in a tool view */}
          {selectedDoc && ['detail','ask','quiz','summarize','mindmap'].includes(view) && (
            <>
              <div style={{
                height: 1,
                background: 'var(--glass-border)',
                margin: '8px 0',
              }} />
              <button
                className={`nav-item ${view === 'detail' ? 'active' : ''}`}
                onClick={() => navigate('detail')}
              >
                <span className="nav-icon">📄</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {selectedDoc.filename || 'Document'}
                </span>
              </button>

              {['ask','quiz','summarize','mindmap'].includes(view) && (
                <button className="nav-item active" style={{ paddingLeft: 28 }}>
                  <span className="nav-icon">
                    {view === 'ask' ? '💬' : view === 'quiz' ? '🧠' : view === 'summarize' ? '📋' : '🗺️'}
                  </span>
                  {view === 'ask' ? 'Q&A' : view === 'quiz' ? 'Quiz' : view === 'summarize' ? 'Summary' : 'Mind Map'}
                </button>
              )}
            </>
          )}
        </nav>

        <div className="sidebar-footer">
          Powered by Spark • Kafka • Qdrant
        </div>
      </aside>

      {/* ─── Main Content ────────────────────────────────── */}
      <main className="main-content">
        <header className="page-header">
          <h2>{info.title}</h2>
          <p>{info.sub}</p>
        </header>

        <div className="page-body">
          {view === 'upload' && (
            <Upload onUploaded={handleUploaded} />
          )}

          {view === 'library' && (
            <DocumentLibrary
              onSelectDoc={handleSelectDoc}
              refreshKey={refreshKey}
            />
          )}

          {view === 'detail' && selectedDoc && (
            <DocumentDetail
              doc={selectedDoc}
              onAction={handleAction}
              onBack={goBackToLibrary}
            />
          )}

          {view === 'ask' && (
            <QAChat doc={selectedDoc} onBack={goBackToDetail} />
          )}

          {view === 'quiz' && (
            <QuizView doc={selectedDoc} onBack={goBackToDetail} />
          )}

          {view === 'summarize' && (
            <SummaryView doc={selectedDoc} onBack={goBackToDetail} />
          )}

          {view === 'mindmap' && (
            <MindMapView doc={selectedDoc} onBack={goBackToDetail} />
          )}
        </div>
      </main>
    </div>
  );
}

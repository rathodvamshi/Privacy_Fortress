import React, { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ChatArea } from './components/ChatArea';
import { InputArea } from './components/InputArea';
import { ToastContainer, addToast } from './components/Toast';
import { useChat } from './hooks/useChat';
import { useSessions } from './hooks/useSessions';
import { AuthProvider, useAuth, clearDraft, saveDraft } from './hooks/useAuth.jsx';

// ── Lazy-loaded heavy components (code-split into separate chunks) ──
const MaskedViewer = lazy(() => import('./components/MaskedViewer').then(m => ({ default: m.MaskedViewer })));
const AuthModal = lazy(() => import('./components/AuthModal').then(m => ({ default: m.AuthModal })));
const ProfilePage = lazy(() => import('./components/ProfilePage').then(m => ({ default: m.ProfilePage })));

// Minimal fallback for lazy-loaded overlays
const LazyFallback = () => (
  <div style={{
    position: 'fixed', inset: 0, display: 'flex',
    alignItems: 'center', justifyContent: 'center',
    background: 'rgba(0,0,0,0.5)', zIndex: 9999
  }}>
    <div className="loading-spinner" />
  </div>
);

/**
 * Main app — chat is ALWAYS visible.
 * - Logged out: Header shows Login / Sign Up buttons. Sending opens auth modal.
 * - Logged in:  Header shows user avatar + dropdown. Full functionality.
 */
function MainApp() {
  const { user, isAuthenticated, logout, isLoading: authLoading } = useAuth();

  const {
    messages,
    sessionId,
    isLoading,
    error,
    tokenCount,
    ttlRemaining,
    sendMessage,
    newChat,
    loadSession,
    clearError,
    stopGenerating,
  } = useChat();

  const {
    sessions,
    groupedSessions,
    loadSessions,
    deleteSession,
    renameSession,
  } = useSessions();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [maskedViewerOpen, setMaskedViewerOpen] = useState(false);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [liveTtl, setLiveTtl] = useState(0);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [pendingMessage, setPendingMessage] = useState(null);
  const [profileOpen, setProfileOpen] = useState(false);

  const chatAreaRef = useRef(null);
  const prevAuthRef = useRef(isAuthenticated);

  // When user logs in → reload sessions & show welcome toast
  useEffect(() => {
    if (isAuthenticated && !prevAuthRef.current) {
      loadSessions();
      addToast(`Welcome${user?.name ? ', ' + user.name : ''}!`, 'success');
    }
    prevAuthRef.current = isAuthenticated;
  }, [isAuthenticated]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (chatAreaRef.current) {
      chatAreaRef.current.scrollTop = chatAreaRef.current.scrollHeight;
    }
  }, [messages]);

  // Reload sessions when a new message is sent
  useEffect(() => {
    if (sessionId && isAuthenticated) {
      loadSessions();
    }
  }, [messages.length]);

  // Live TTL countdown
  useEffect(() => {
    setLiveTtl(ttlRemaining);
  }, [ttlRemaining]);

  useEffect(() => {
    if (liveTtl <= 0) return;
    const interval = setInterval(() => {
      setLiveTtl(prev => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [liveTtl > 0]);

  // Auto-dismiss errors
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => clearError?.(), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (authModalOpen) {
          setAuthModalOpen(false);
        } else if (maskedViewerOpen) {
          setMaskedViewerOpen(false);
          setSelectedMessage(null);
        } else if (sidebarOpen && window.innerWidth < 768) {
          setSidebarOpen(false);
        }
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
        e.preventDefault();
        setSidebarOpen(prev => !prev);
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'N') {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [maskedViewerOpen, sidebarOpen, authModalOpen]);

  // ── Handlers ────────────────────────────────────────

  const handleSelectSession = (id) => {
    loadSession(id);
    setMaskedViewerOpen(false);
    setSelectedMessage(null);
    if (window.innerWidth < 768) setSidebarOpen(false);
  };

  const handleNewChat = () => {
    newChat();
    setMaskedViewerOpen(false);
    setSelectedMessage(null);
    if (window.innerWidth < 768) setSidebarOpen(false);
  };

  const handleDeleteSession = async (id) => {
    const success = await deleteSession(id);
    if (success && id === sessionId) {
      newChat();
    }
  };

  const handleRenameSession = async (id, title) => {
    await renameSession(id, title);
  };

  const handleViewMasked = (message) => {
    setSelectedMessage(message);
    setMaskedViewerOpen(true);
  };

  const handleSuggestionClick = (text) => {
    handleSendMessage(text);
  };

  /**
   * Central send handler — intercepts if not logged in.
   * Saves the message as draft, opens auth modal.
   * After login the pending message auto-sends via useEffect.
   */
  const handleSendMessage = useCallback((text) => {
    if (!isAuthenticated) {
      setPendingMessage(text);
      saveDraft(text);
      setAuthModalOpen(true);
      return;
    }
    sendMessage(text);
  }, [isAuthenticated, sendMessage]);

  const handleAuthSuccess = () => {
    setAuthModalOpen(false);
    // Send pending message directly — the access token is already set
    // on the api module by login/signup, so the request will be authenticated.
    if (pendingMessage) {
      sendMessage(pendingMessage);
      setPendingMessage(null);
      clearDraft();
    }
  };

  const handleLogout = () => {
    logout();
    newChat();
    addToast('Logged out successfully', 'info');
  };

  const handleOpenAuthModal = () => {
    setAuthModalOpen(true);
  };

  const toggleSidebar = () => setSidebarOpen(prev => !prev);

  // Show loading while checking stored token
  if (authLoading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading-inner">
          <div className="loading-spinner" />
          <p>Loading Privacy Fortress…</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`app ${sidebarOpen && isAuthenticated ? 'sidebar-open' : 'sidebar-closed'}`}>
      {isAuthenticated && (
        <Sidebar
          sessions={sessions}
          groupedSessions={groupedSessions}
          activeSessionId={sessionId}
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          onRenameSession={handleRenameSession}
          isOpen={sidebarOpen}
          onToggle={toggleSidebar}
        />
      )}

      <main className="main-content">
        <Header
          tokenCount={tokenCount}
          ttlRemaining={liveTtl}
          user={user}
          isAuthenticated={isAuthenticated}
          onLogout={handleLogout}
          onOpenAuth={handleOpenAuthModal}
          onOpenProfile={() => setProfileOpen(true)}
          sidebarOpen={sidebarOpen && isAuthenticated}
          onToggleSidebar={toggleSidebar}
          onNewChat={handleNewChat}
        />

        <div ref={chatAreaRef} className="chat-scroll-area">
          <ChatArea
            messages={messages}
            isLoading={isLoading}
            onViewMasked={handleViewMasked}
            onSuggestionClick={handleSuggestionClick}
          />
        </div>

        {error && (
          <div className="error-banner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="15" y1="9" x2="9" y2="15"></line>
              <line x1="9" y1="9" x2="15" y2="15"></line>
            </svg>
            <span>{error}</span>
            <button className="error-dismiss" onClick={clearError}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        )}

        <InputArea
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          disabled={false}
          onStopGenerating={stopGenerating}
        />
      </main>

      {maskedViewerOpen && (
        <Suspense fallback={<LazyFallback />}>
          <MaskedViewer
            message={selectedMessage}
            sessionId={sessionId}
            isOpen={maskedViewerOpen}
            onClose={() => {
              setMaskedViewerOpen(false);
              setSelectedMessage(null);
            }}
          />
        </Suspense>
      )}

      <Suspense fallback={<LazyFallback />}>
        <AuthModal
          isOpen={authModalOpen}
          onClose={() => {
            setAuthModalOpen(false);
            setPendingMessage(null);
          }}
          onSuccess={handleAuthSuccess}
        />
      </Suspense>

      {profileOpen && (
        <Suspense fallback={<LazyFallback />}>
          <ProfilePage onClose={() => setProfileOpen(false)} />
        </Suspense>
      )}

      <ToastContainer />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}

export default App;

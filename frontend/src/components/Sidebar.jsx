import React, { useState, useRef, useEffect } from 'react';
import { addToast } from './Toast';

export function Sidebar({
    sessions,
    groupedSessions,
    activeSessionId,
    onNewChat,
    onSelectSession,
    onDeleteSession,
    onRenameSession,
    isOpen,
    onToggle,
}) {
    const [searchQuery, setSearchQuery] = useState('');
    const [hoveredSession, setHoveredSession] = useState(null);
    const [confirmDelete, setConfirmDelete] = useState(null);
    const [editingSession, setEditingSession] = useState(null);
    const [editTitle, setEditTitle] = useState('');
    const renameInputRef = useRef(null);

    // Focus rename input when editing starts
    useEffect(() => {
        if (editingSession && renameInputRef.current) {
            renameInputRef.current.focus();
            renameInputRef.current.select();
        }
    }, [editingSession]);

    const filterSessions = (items) => {
        if (!searchQuery.trim()) return items;
        return items.filter(s =>
            (s.title || 'New Chat').toLowerCase().includes(searchQuery.toLowerCase())
        );
    };

    const handleDelete = (e, sessionId) => {
        e.stopPropagation();
        if (confirmDelete === sessionId) {
            onDeleteSession?.(sessionId);
            setConfirmDelete(null);
            addToast('Conversation deleted', 'success', 2000);
        } else {
            setConfirmDelete(sessionId);
            setTimeout(() => setConfirmDelete(null), 3000);
        }
    };

    const handleStartRename = (e, session) => {
        e.stopPropagation();
        setEditingSession(session.id);
        setEditTitle(session.title || 'New Chat');
    };

    const handleRenameSubmit = (e, sessionId) => {
        e?.preventDefault();
        if (editTitle.trim()) {
            onRenameSession?.(sessionId, editTitle.trim());
            addToast('Conversation renamed', 'success', 2000);
        }
        setEditingSession(null);
    };

    const handleRenameKeyDown = (e, sessionId) => {
        if (e.key === 'Enter') {
            handleRenameSubmit(e, sessionId);
        } else if (e.key === 'Escape') {
            setEditingSession(null);
        }
    };

    return (
        <>
            {isOpen && <div className="sidebar-overlay" onClick={onToggle} />}

            <aside className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
                <div className="sidebar-top">
                    <div className="sidebar-top-row">
                        <button className="sidebar-toggle-btn" onClick={onToggle} title="Close sidebar">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                                <line x1="9" y1="3" x2="9" y2="21"></line>
                            </svg>
                        </button>
                        <button className="new-chat-btn" onClick={onNewChat} title="New chat">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 5v14M5 12h14"></path>
                            </svg>
                        </button>
                    </div>

                    <div className="sidebar-search">
                        <svg className="sidebar-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="11" cy="11" r="8"></circle>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                        <input
                            type="text"
                            className="sidebar-search-input"
                            placeholder="Search conversations..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                        {searchQuery && (
                            <button className="sidebar-search-clear" onClick={() => setSearchQuery('')}>✕</button>
                        )}
                    </div>
                </div>

                <div className="sessions-list">
                    {Object.entries(groupedSessions).map(([group, items]) => {
                        const filtered = filterSessions(items);
                        if (filtered.length === 0) return null;
                        return (
                            <div key={group} className="sessions-group">
                                <div className="sessions-group-title">{group}</div>
                                {filtered.map(session => (
                                    <div
                                        key={session.id}
                                        className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                                        onClick={() => { if (editingSession !== session.id) onSelectSession(session.id); }}
                                        onMouseEnter={() => setHoveredSession(session.id)}
                                        onMouseLeave={() => { setHoveredSession(null); if (confirmDelete === session.id) setConfirmDelete(null); }}
                                    >
                                        <svg className="session-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                                        </svg>
                                        {editingSession === session.id ? (
                                            <input
                                                ref={renameInputRef}
                                                className="session-rename-input"
                                                value={editTitle}
                                                onChange={(e) => setEditTitle(e.target.value)}
                                                onBlur={(e) => handleRenameSubmit(e, session.id)}
                                                onKeyDown={(e) => handleRenameKeyDown(e, session.id)}
                                                onClick={(e) => e.stopPropagation()}
                                            />
                                        ) : (
                                            <span className="session-title">{session.title || 'New Chat'}</span>
                                        )}
                                        {hoveredSession === session.id && editingSession !== session.id && (
                                            <div className="session-actions">
                                                <button
                                                    className="session-action-btn"
                                                    onClick={(e) => handleStartRename(e, session)}
                                                    title="Rename"
                                                >
                                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                                                    </svg>
                                                </button>
                                                <button
                                                    className={`session-action-btn ${confirmDelete === session.id ? 'confirm-delete' : ''}`}
                                                    onClick={(e) => handleDelete(e, session.id)}
                                                    title={confirmDelete === session.id ? 'Click again to confirm' : 'Delete'}
                                                >
                                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                        <polyline points="3 6 5 6 21 6"></polyline>
                                                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                                    </svg>
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        );
                    })}

                    {sessions.length === 0 && (
                        <div className="sessions-empty">
                            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                            </svg>
                            <p>No conversations yet</p>
                            <span>Start a new chat to begin</span>
                        </div>
                    )}

                    {searchQuery && Object.entries(groupedSessions).every(([, items]) => filterSessions(items).length === 0) && (
                        <div className="sessions-empty">
                            <p>No results found</p>
                            <span>Try a different search term</span>
                        </div>
                    )}
                </div>

                <div className="sidebar-bottom">
                    <div className="sidebar-bottom-item">
                        <img src="/logo.jpg" alt="Privacy Fortress" className="sidebar-logo" />
                        <span>Privacy Fortress v1.0</span>
                    </div>
                </div>
            </aside>
        </>
    );
}

export default Sidebar;

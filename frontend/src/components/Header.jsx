import React, { useState, useRef, useEffect } from 'react';

export function Header({ tokenCount, ttlRemaining, user, isAuthenticated, onLogout, onOpenAuth, onOpenProfile, sidebarOpen, onToggleSidebar, onNewChat }) {
    const [menuOpen, setMenuOpen] = useState(false);
    const menuRef = useRef(null);

    const formatTime = (seconds) => {
        if (seconds <= 0) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // Close menu on outside click
    useEffect(() => {
        if (!menuOpen) return;
        const handler = (e) => {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                setMenuOpen(false);
            }
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [menuOpen]);

    const userInitial = user?.name ? user.name.charAt(0).toUpperCase() : user?.email?.charAt(0).toUpperCase() || '?';

    return (
        <header className="header">
            <div className="header-left">
                {isAuthenticated && !sidebarOpen && (
                    <button className="header-sidebar-toggle" onClick={onToggleSidebar} title="Open sidebar">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="9" y1="3" x2="9" y2="21"></line>
                        </svg>
                    </button>
                )}
                {isAuthenticated && !sidebarOpen && (
                    <button className="header-new-chat" onClick={onNewChat} title="New chat">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 5v14M5 12h14"></path>
                        </svg>
                    </button>
                )}
                <div className="header-title">
                    <img src="/logo.jpg" alt="Privacy Fortress" className="header-logo" />
                    Privacy Fortress
                </div>
            </div>

            <div className="header-center">
                <div className="header-model-badge">
                    <span className="header-model-dot"></span>
                    Zero-Knowledge Mode
                </div>
            </div>

            <div className="header-right">
                {tokenCount > 0 && (
                    <div className="header-badge tokens">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                        </svg>
                        {tokenCount} tokens masked
                    </div>
                )}

                {ttlRemaining > 0 && (
                    <div className="header-badge ttl">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        {formatTime(ttlRemaining)}
                    </div>
                )}

                <div className="header-badge encryption">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                    AES-256
                </div>

                {/* Conditional: Login/Signup buttons OR User dropdown */}
                {!isAuthenticated ? (
                    <div className="header-auth-buttons">
                        <button
                            className="header-auth-btn login"
                            onClick={onOpenAuth}
                        >
                            Log In
                        </button>
                        <button
                            className="header-auth-btn signup"
                            onClick={onOpenAuth}
                        >
                            Sign Up
                        </button>
                    </div>
                ) : (
                    <div className="profile-dropdown-wrapper" ref={menuRef}>
                        <button
                            className="profile-btn"
                            onClick={() => setMenuOpen(!menuOpen)}
                            title={user?.name || user?.email || 'Profile'}
                        >
                            <span className="profile-avatar">{userInitial}</span>
                        </button>

                        {menuOpen && (
                            <div className="profile-dropdown">
                                <div className="profile-dropdown-header">
                                    <span className="profile-dropdown-avatar">{userInitial}</span>
                                    <div className="profile-dropdown-info">
                                        <span className="profile-dropdown-name">{user?.name || 'User'}</span>
                                        <span className="profile-dropdown-email">{user?.email}</span>
                                    </div>
                                </div>
                                <div className="profile-dropdown-divider" />
                                <button className="profile-dropdown-item" onClick={() => { setMenuOpen(false); onOpenProfile(); }}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                                        <circle cx="12" cy="7" r="4"></circle>
                                    </svg>
                                    My Profile
                                </button>
                                <div className="profile-dropdown-divider" />
                                <button className="profile-dropdown-item logout" onClick={() => { setMenuOpen(false); onLogout(); }}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                                        <polyline points="16 17 21 12 16 7"></polyline>
                                        <line x1="21" y1="12" x2="9" y2="12"></line>
                                    </svg>
                                    Log Out
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </header>
    );
}

export default Header;

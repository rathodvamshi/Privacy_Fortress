import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth.jsx';

/**
 * AuthModal — slide-up overlay for Login / Sign Up.
 * Triggered when a guest user tries to send a message.
 * On success, calls onSuccess callback (which auto-sends the pending message).
 */
export function AuthModal({ isOpen, onClose, onSuccess }) {
    const { login, signup, error, clearAuthError } = useAuth();
    const [mode, setMode] = useState('login');
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [localError, setLocalError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    const emailRef = useRef(null);
    const nameRef = useRef(null);
    const overlayRef = useRef(null);

    // Focus on open
    useEffect(() => {
        if (isOpen) {
            setTimeout(() => {
                if (mode === 'signup') {
                    nameRef.current?.focus();
                } else {
                    emailRef.current?.focus();
                }
            }, 100);
        }
    }, [isOpen, mode]);

    // Reset on mode change
    useEffect(() => {
        clearAuthError();
        setLocalError('');
    }, [mode]);

    // Close on Escape
    useEffect(() => {
        if (!isOpen) return;
        const handleKey = (e) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKey);
        return () => window.removeEventListener('keydown', handleKey);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    const switchMode = (newMode) => {
        setMode(newMode);
        setPassword('');
        setConfirmPassword('');
        setLocalError('');
        clearAuthError();
    };

    const validate = () => {
        if (mode === 'signup') {
            if (!name.trim()) return 'Name is required';
            if (name.trim().length < 2) return 'Name must be at least 2 characters';
        }
        if (!email.trim()) return 'Email is required';
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Enter a valid email';
        if (!password) return 'Password is required';
        if (password.length < 6) return 'Password must be at least 6 characters';
        if (mode === 'signup' && password !== confirmPassword) return 'Passwords do not match';
        return null;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLocalError('');
        clearAuthError();

        const err = validate();
        if (err) {
            setLocalError(err);
            return;
        }

        setIsSubmitting(true);
        try {
            let success = false;
            if (mode === 'login') {
                success = await login(email.trim().toLowerCase(), password);
            } else {
                success = await signup(name.trim(), email.trim().toLowerCase(), password);
            }
            if (success) {
                onSuccess?.();
                // Don't call onClose here — onSuccess handles closing
                // the modal and sending the pending message.
            }
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleOverlayClick = (e) => {
        if (e.target === overlayRef.current) onClose();
    };

    const displayError = localError || error;

    return (
        <div className="auth-modal-overlay" ref={overlayRef} onClick={handleOverlayClick}>
            <div className="auth-modal">
                {/* Close button */}
                <button className="auth-modal-close" onClick={onClose} type="button">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>

                {/* Header */}
                <div className="auth-modal-header">
                    <div className="auth-modal-icon">
                        <img src="/logo.jpg" alt="Privacy Fortress" className="auth-modal-logo-img" />
                    </div>
                    <h2 className="auth-modal-title">
                        {mode === 'login' ? 'Welcome Back' : 'Create Account'}
                    </h2>
                    <p className="auth-modal-subtitle">
                        Sign in to send messages with privacy protection
                    </p>
                </div>

                {/* Tabs */}
                <div className="auth-tabs">
                    <button
                        className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
                        onClick={() => switchMode('login')}
                        type="button"
                    >
                        Log In
                    </button>
                    <button
                        className={`auth-tab ${mode === 'signup' ? 'active' : ''}`}
                        onClick={() => switchMode('signup')}
                        type="button"
                    >
                        Sign Up
                    </button>
                </div>

                {/* Form */}
                <form className="auth-form" onSubmit={handleSubmit} noValidate>
                    {mode === 'signup' && (
                        <div className="auth-field">
                            <label className="auth-label" htmlFor="modal-auth-name">Full Name</label>
                            <div className="auth-input-wrapper">
                                <svg className="auth-input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                                    <circle cx="12" cy="7" r="4"></circle>
                                </svg>
                                <input
                                    ref={nameRef}
                                    id="modal-auth-name"
                                    type="text"
                                    className="auth-input"
                                    placeholder="John Doe"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    autoComplete="name"
                                />
                            </div>
                        </div>
                    )}

                    <div className="auth-field">
                        <label className="auth-label" htmlFor="modal-auth-email">Email</label>
                        <div className="auth-input-wrapper">
                            <svg className="auth-input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                                <polyline points="22,6 12,13 2,6"></polyline>
                            </svg>
                            <input
                                ref={emailRef}
                                id="modal-auth-email"
                                type="email"
                                className="auth-input"
                                placeholder="you@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                autoComplete="email"
                            />
                        </div>
                    </div>

                    <div className="auth-field">
                        <label className="auth-label" htmlFor="modal-auth-password">Password</label>
                        <div className="auth-input-wrapper">
                            <svg className="auth-input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                            </svg>
                            <input
                                id="modal-auth-password"
                                type={showPassword ? 'text' : 'password'}
                                className="auth-input"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                            />
                            <button
                                type="button"
                                className="auth-password-toggle"
                                onClick={() => setShowPassword(!showPassword)}
                                tabIndex={-1}
                            >
                                {showPassword ? (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                                        <line x1="1" y1="1" x2="23" y2="23"></line>
                                    </svg>
                                ) : (
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                        <circle cx="12" cy="12" r="3"></circle>
                                    </svg>
                                )}
                            </button>
                        </div>
                    </div>

                    {mode === 'signup' && (
                        <div className="auth-field">
                            <label className="auth-label" htmlFor="modal-auth-confirm">Confirm Password</label>
                            <div className="auth-input-wrapper">
                                <svg className="auth-input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                                <input
                                    id="modal-auth-confirm"
                                    type={showPassword ? 'text' : 'password'}
                                    className="auth-input"
                                    placeholder="••••••••"
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    autoComplete="new-password"
                                />
                            </div>
                        </div>
                    )}

                    {displayError && (
                        <div className="auth-error">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <line x1="15" y1="9" x2="9" y2="15"></line>
                                <line x1="9" y1="9" x2="15" y2="15"></line>
                            </svg>
                            <span>{displayError}</span>
                        </div>
                    )}

                    <button
                        type="submit"
                        className="auth-submit"
                        disabled={isSubmitting}
                    >
                        {isSubmitting ? (
                            <div className="loading-spinner small" />
                        ) : (
                            mode === 'login' ? 'Log In' : 'Create Account'
                        )}
                    </button>
                </form>

                {/* Features */}
                <div className="auth-features" style={{ justifyContent: 'center', paddingTop: '4px' }}>
                    <div className="auth-feature">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                        </svg>
                        AES-256
                    </div>
                    <div className="auth-feature">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        Auto-Delete
                    </div>
                    <div className="auth-feature">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                        Zero-Knowledge
                    </div>
                </div>
            </div>
        </div>
    );
}

export default AuthModal;

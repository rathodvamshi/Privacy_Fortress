import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { MarkdownRenderer } from './MarkdownRenderer';

export function MaskedViewer({ message, sessionId, isOpen, onClose }) {
    const [maskedData, setMaskedData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [activeSection, setActiveSection] = useState('flow'); // 'flow' | 'tokens'

    useEffect(() => {
        if (isOpen && message && sessionId) {
            loadMaskedData();
        }
        if (!isOpen) {
            setMaskedData(null);
            setError(null);
            setActiveSection('flow');
        }
    }, [isOpen, message?.id, sessionId]);

    const loadMaskedData = async () => {
        if (!message || !sessionId) return;
        setIsLoading(true);
        setError(null);
        try {
            const data = await api.getMaskedPrompt(sessionId, message.id);
            setMaskedData(data);
        } catch (err) {
            console.error('Failed to load masked data:', err);
            setError(err.message || 'Failed to load masked data');
        } finally {
            setIsLoading(false);
        }
    };

    const formatTime = (seconds) => {
        if (!seconds || seconds <= 0) return 'Expired';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const getTypeColor = (type) => {
        const colors = {
            'USER': '#3b82f6',
            'PERSON': '#3b82f6',
            'COLLEGE': '#0ea5e9',
            'EMAIL': '#8b5cf6',
            'PHONE': '#10b981',
            'LOCATION': '#f59e0b',
            'LOC': '#f59e0b',
            'ORG': '#ef4444',
            'DATE': '#ec4899',
            'GPE': '#f59e0b',
            'NUMBER': '#06b6d4',
            'NUM': '#06b6d4',
        };
        return colors[type?.toUpperCase()] || '#6b7280';
    };

    const getTypeEmoji = (type) => {
        const emojis = {
            'USER': '👤',
            'PERSON': '👤',
            'COLLEGE': '🎓',
            'EMAIL': '📧',
            'PHONE': '📱',
            'LOCATION': '📍',
            'LOC': '📍',
            'ORG': '🏢',
            'DATE': '📅',
            'GPE': '🌍',
            'NUMBER': '#️⃣',
            'NUM': '#️⃣',
        };
        return emojis[type?.toUpperCase()] || '🔒';
    };

    /** Highlight tokens in text by wrapping them in styled spans. */
    const highlightTokens = (text, tokens) => {
        if (!text || !tokens || tokens.length === 0) return text;
        const tokenNames = tokens.map(t => t.token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
        if (tokenNames.length === 0) return text;
        const regex = new RegExp(`(${tokenNames.join('|')})`, 'g');
        const parts = text.split(regex);
        return parts.map((part, i) => {
            const tokenMatch = tokens.find(t => t.token === part);
            if (tokenMatch) {
                return (
                    <span
                        key={i}
                        className="mv-token-highlight"
                        style={{ '--token-color': getTypeColor(tokenMatch.type) }}
                        title={`${tokenMatch.type}: ${tokenMatch.original_value || tokenMatch.display}`}
                    >
                        {part}
                    </span>
                );
            }
            return part;
        });
    };

    if (!isOpen) return null;

    return (
        <aside className="mv-panel">
            {/* Header */}
            <div className="mv-header">
                <div className="mv-header-left">
                    <div className="mv-header-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    </div>
                    <div>
                        <div className="mv-header-title">Masked Prompt Viewer</div>
                        <div className="mv-header-sub">See exactly what the AI saw vs what you see</div>
                    </div>
                </div>
                <button className="mv-close" onClick={onClose} title="Close viewer">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>

            {/* Tab Switcher */}
            <div className="mv-tabs">
                <button className={`mv-tab ${activeSection === 'flow' ? 'active' : ''}`} onClick={() => setActiveSection('flow')}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                    Data Flow
                </button>
                <button className={`mv-tab ${activeSection === 'tokens' ? 'active' : ''}`} onClick={() => setActiveSection('tokens')}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                    Tokens ({maskedData?.tokens?.length || 0})
                </button>
            </div>

            {/* Content */}
            <div className="mv-body">
                {isLoading ? (
                    <div className="mv-loading">
                        <div className="mv-loading-ring"></div>
                        <p>Loading transparency data…</p>
                    </div>
                ) : error ? (
                    <div className="mv-error">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
                        <p>{error}</p>
                        <button className="mv-retry-btn" onClick={loadMaskedData}>Try again</button>
                    </div>
                ) : maskedData ? (
                    <>
                        {/* ── DATA FLOW TAB ── */}
                        {activeSection === 'flow' && (
                            <div className="mv-flow" key="flow">
                                <p className="mv-flow-intro">How your message and the AI reply are handled — from your words to placeholders and back.</p>

                                {/* Step 1: Your message as you typed it */}
                                <div className="mv-step">
                                    <div className="mv-step-badge">
                                        <span className="mv-step-num">1</span>
                                        <span className="mv-step-line"></span>
                                    </div>
                                    <div className="mv-step-card">
                                        <div className="mv-step-label">
                                            <span className="mv-step-emoji">📥</span>
                                            Your message (as you typed it)
                                        </div>
                                        <div className="mv-step-content original">
                                            {maskedData.original_message || '—'}
                                        </div>
                                    </div>
                                </div>

                                {/* Step 2: PII detected and tokenized */}
                                {maskedData.tokens && maskedData.tokens.length > 0 && (
                                    <div className="mv-step">
                                        <div className="mv-step-badge">
                                            <span className="mv-step-num">2</span>
                                            <span className="mv-step-line"></span>
                                        </div>
                                        <div className="mv-step-card">
                                            <div className="mv-step-label">
                                                <span className="mv-step-emoji">🔍</span>
                                                Detected PII → tokens (labels)
                                            </div>
                                            <div className="mv-detections">
                                                {maskedData.tokens.map((t, i) => (
                                                    <div className="mv-detection-row" key={i}>
                                                        <span className="mv-detection-emoji">{getTypeEmoji(t.type)}</span>
                                                        <span className="mv-detection-original">{t.original_value || t.display}</span>
                                                        <span className="mv-detection-arrow">→</span>
                                                        <span className="mv-detection-token" style={{ color: getTypeColor(t.type) }}>{t.token}</span>
                                                        <span className="mv-detection-type" style={{ background: getTypeColor(t.type) + '18', color: getTypeColor(t.type) }}>{t.type}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Step 3: What the AI received (your prompt masked) */}
                                <div className="mv-step">
                                    <div className="mv-step-badge">
                                        <span className="mv-step-num">{maskedData.tokens?.length > 0 ? '3' : '2'}</span>
                                        <span className="mv-step-line"></span>
                                    </div>
                                    <div className="mv-step-card">
                                        <div className="mv-step-label">
                                            <span className="mv-step-emoji">🎭</span>
                                            What the AI received (your prompt — masked)
                                        </div>
                                        <div className="mv-step-content masked">
                                            {highlightTokens(maskedData.masked_message || '—', maskedData.tokens)}
                                        </div>
                                    </div>
                                </div>

                                {/* AI Response block: masked + unmasked */}
                                <div className="mv-ai-response-block">
                                    <div className="mv-ai-response-heading">
                                        <span className="mv-step-emoji">🤖</span>
                                        AI response
                                    </div>

                                    <div className="mv-ai-response-row masked">
                                        <div className="mv-ai-response-sublabel">Stored / what the model produced (placeholders only)</div>
                                        <div className="mv-step-content ai-masked">
                                            {highlightTokens(maskedData.ai_masked_response || '—', maskedData.tokens)}
                                        </div>
                                    </div>

                                    <div className="mv-ai-response-row unmasked">
                                        <div className="mv-ai-response-sublabel">What you see (unmasked in backend, then shown here)</div>
                                        <div className="mv-step-content unmasked mv-response-final">
                                            {maskedData.ai_unmasked_response && maskedData.ai_unmasked_response.trim() ? (
                                                <MarkdownRenderer content={maskedData.ai_unmasked_response} fallback={maskedData.ai_unmasked_response} />
                                            ) : (
                                                '—'
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ── TOKENS TAB ── */}
                        {activeSection === 'tokens' && (
                            <div className="mv-tokens-panel" key="tokens">
                                {maskedData.tokens && maskedData.tokens.length > 0 ? (
                                    <>
                                        <p className="mv-tokens-intro">All PII detected in this exchange, with token label and original value (visible only to you).</p>
                                        <div className="mv-tokens-header-row">
                                            <span>Token</span>
                                            <span>Original value</span>
                                            <span>Type</span>
                                        </div>
                                        {maskedData.tokens.map((t, i) => (
                                            <div className="mv-token-row" key={i}>
                                                <div className="mv-token-name" style={{ color: getTypeColor(t.type) }}>
                                                    {t.token}
                                                </div>
                                                <div className="mv-token-original">
                                                    {t.original_value || t.display}
                                                </div>
                                                <div className="mv-token-type-badge" style={{
                                                    background: getTypeColor(t.type) + '15',
                                                    color: getTypeColor(t.type),
                                                    borderColor: getTypeColor(t.type) + '30',
                                                }}>
                                                    {getTypeEmoji(t.type)} {t.type}
                                                </div>
                                            </div>
                                        ))}
                                        <div className="mv-tokens-summary">
                                            <div className="mv-tokens-summary-item">
                                                <span className="mv-tokens-summary-num">{maskedData.tokens.length}</span>
                                                <span>PII items masked</span>
                                            </div>
                                            <div className="mv-tokens-summary-item">
                                                <span className="mv-tokens-summary-num" style={{ color: '#10b981' }}>
                                                    {[...new Set(maskedData.tokens.map(t => t.type))].length}
                                                </span>
                                                <span>Entity types</span>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <div className="mv-empty">
                                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
                                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                                        </svg>
                                        <p>No PII detected in this message</p>
                                        <span>Nothing was masked; the message was sent as-is to the model.</span>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                ) : (
                    <div className="mv-empty">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                        <p>Select a message to view masked details</p>
                        <span>Click “View Masked Prompt” on an AI reply to see the data flow.</span>
                    </div>
                )}
            </div>

            {/* Footer */}
            {maskedData && (
                <div className="mv-footer">
                    <div className="mv-footer-item">
                        <span>🔒</span>
                        {maskedData.encryption_status?.algorithm || 'AES-256-GCM'}
                    </div>
                    <div className="mv-footer-divider"></div>
                    <div className="mv-footer-item">
                        <span>⏱️</span>
                        Session TTL {formatTime(maskedData.ttl_remaining)}
                    </div>
                    <div className="mv-footer-divider"></div>
                    <div className="mv-footer-item accent">
                        <span>✓</span>
                        AI never saw your PII
                    </div>
                </div>
            )}
        </aside>
    );
}

export default MaskedViewer;

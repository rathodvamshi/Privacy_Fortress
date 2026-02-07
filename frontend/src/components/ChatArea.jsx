import React, { useEffect, useRef } from 'react';
import Message from './Message';

const SUGGESTION_CARDS = [
    {
        icon: (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
        ),
        title: 'Write an email',
        subtitle: 'with personal details safely masked',
    },
    {
        icon: (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
        ),
        title: 'Ask about privacy',
        subtitle: 'and how your data stays protected',
    },
    {
        icon: (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="16 18 22 12 16 6"></polyline>
                <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
        ),
        title: 'Debug some code',
        subtitle: 'share code snippets with confidence',
    },
    {
        icon: (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
            </svg>
        ),
        title: 'Have a conversation',
        subtitle: 'your identity stays anonymous',
    },
];

export function ChatArea({ messages, isLoading, onViewMasked, onSuggestionClick }) {
    const messagesEndRef = useRef(null);

    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isLoading]);

    if (messages.length === 0 && !isLoading) {
        return (
            <div className="chat-area">
                <div className="chat-empty">
                    <div className="chat-empty-logo">
                        <img src="/logo.jpg" alt="Privacy Fortress" className="chat-empty-logo-img" />
                    </div>
                    <h2 className="chat-empty-title">What can I help with?</h2>
                    <p className="chat-empty-subtitle">
                        Your messages are automatically masked — names, emails, phone numbers & more are replaced with tokens before reaching the AI.
                    </p>

                    <div className="suggestion-grid">
                        {SUGGESTION_CARDS.map((card, i) => (
                            <button
                                key={i}
                                className="suggestion-card"
                                onClick={() => onSuggestionClick?.(card.title)}
                            >
                                <div className="suggestion-card-icon">{card.icon}</div>
                                <div className="suggestion-card-text">
                                    <div className="suggestion-card-title">{card.title}</div>
                                    <div className="suggestion-card-subtitle">{card.subtitle}</div>
                                </div>
                            </button>
                        ))}
                    </div>

                    <div className="privacy-features">
                        <div className="privacy-feature">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                            </svg>
                            AES-256 encrypted vault
                        </div>
                        <div className="privacy-feature">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10"></circle>
                                <polyline points="12 6 12 12 16 14"></polyline>
                            </svg>
                            Auto-deletes in 30 min
                        </div>
                        <div className="privacy-feature">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                                <circle cx="12" cy="12" r="3"></circle>
                            </svg>
                            Zero-knowledge architecture
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="chat-area">
            <div className="messages-container">
                {messages.map((message, index) => (
                    <Message
                        key={message.id || index}
                        message={message}
                        onViewMasked={onViewMasked}
                    />
                ))}

                {isLoading && (
                    <div className="message assistant-message">
                        <div className="message-avatar assistant">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                            </svg>
                        </div>
                        <div className="message-content">
                            <div className="typing-indicator">
                                <span className="typing-dot"></span>
                                <span className="typing-dot"></span>
                                <span className="typing-dot"></span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>
        </div>
    );
}

export default ChatArea;

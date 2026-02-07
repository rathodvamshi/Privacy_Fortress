import React, { useState } from 'react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { addToast } from './Toast';

// Display text for assistant - always use content (unmasked), never masked_content

export function Message({ message, onViewMasked }) {
    const isUser = message.role === 'user';
    const [showActions, setShowActions] = useState(false);

    const formatTime = (timestamp) => {
        try {
            const date = new Date(timestamp || Date.now());
            if (isNaN(date.getTime())) return '';
            return date.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
        } catch (e) {
            console.error('Time format error:', e);
            return '';
        }
    };

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(message.content);
            addToast('Copied to clipboard', 'success', 2000);
        } catch {
            addToast('Failed to copy', 'error', 2000);
        }
    };

    // Use content (unmasked) for display - NEVER masked_content
    const displayText = isUser ? message.content : (message.content ?? '');

    if (!message) return null;

    return (
        <div className="message">
            <div
                className={`message-inner ${isUser ? 'user-message' : 'assistant-message'}`}
                onMouseEnter={() => setShowActions(true)}
                onMouseLeave={() => setShowActions(false)}
            >
                <div className={`message-avatar ${isUser ? 'user' : 'assistant'}`}>
                    {isUser ? (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                            <circle cx="12" cy="7" r="4"></circle>
                        </svg>
                    ) : (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                        </svg>
                    )}
                </div>

                <div className="message-content" style={{ minWidth: '0' }}>
                    <div className="message-header">
                        <span className="message-sender">
                            {isUser ? 'You' : 'Privacy Fortress AI'}
                        </span>
                        <span className="message-time">
                            {formatTime(message.timestamp)}
                        </span>
                    </div>

                    <div className="message-text assistant-message-body">
                        {isUser ? (
                            displayText
                        ) : (
                            displayText ? (
                                <MarkdownRenderer content={displayText} fallback={displayText} />
                            ) : (
                                <span className="message-empty">(No response received)</span>
                            )
                        )}
                    </div>

                    <div className={`message-toolbar ${showActions ? 'visible' : ''}`}>
                        {!isUser && (
                            <button
                                className="toolbar-btn"
                                onClick={handleCopy}
                                title="Copy response"
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                </svg>
                                Copy
                            </button>
                        )}
                        {!isUser && message.masked_content && (
                            <button
                                className="toolbar-btn masked-btn"
                                onClick={() => onViewMasked(message)}
                                title="View what the AI actually saw"
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path>
                                    <circle cx="12" cy="12" r="3"></circle>
                                </svg>
                                View Masked Prompt
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default Message;

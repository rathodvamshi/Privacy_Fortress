import React, { useState, useRef, useEffect } from 'react';

export function InputArea({ onSendMessage, isLoading, disabled, onStopGenerating }) {
    const [input, setInput] = useState('');
    const textareaRef = useRef(null);

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
            textareaRef.current.style.height = newHeight + 'px';
        }
    }, [input]);

    // Focus textarea on mount
    useEffect(() => {
        textareaRef.current?.focus();
    }, []);

    // Re-focus after loading completes
    useEffect(() => {
        if (!isLoading) {
            setTimeout(() => textareaRef.current?.focus(), 50);
        }
    }, [isLoading]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (input.trim() && !isLoading && !disabled) {
            onSendMessage(input);
            setInput('');
            // Reset height
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    return (
        <div className="input-area">
            {isLoading && (
                <button
                    className="stop-generating-btn"
                    onClick={onStopGenerating}
                    type="button"
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                        <rect x="4" y="4" width="16" height="16" rx="2" />
                    </svg>
                    Stop generating
                </button>
            )}

            <form className="input-container" onSubmit={handleSubmit}>
                <div className="input-wrapper">
                    <textarea
                        ref={textareaRef}
                        className="message-input"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Message Privacy Fortress..."
                        rows={1}
                        disabled={isLoading || disabled}
                    />
                    <button
                        type="submit"
                        className={`send-btn ${input.trim() ? 'active' : ''}`}
                        disabled={!input.trim() || isLoading || disabled}
                    >
                        {isLoading ? (
                            <div className="loading-spinner small"></div>
                        ) : (
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <line x1="12" y1="19" x2="12" y2="5"></line>
                                <polyline points="5 12 12 5 19 12"></polyline>
                            </svg>
                        )}
                    </button>
                </div>
            </form>

            <div className="input-footer">
                <span className="input-footer-text">
                    Privacy Fortress auto-masks PII before it reaches the AI. Your data never leaves unprotected.
                </span>
            </div>
        </div>
    );
}

export default InputArea;

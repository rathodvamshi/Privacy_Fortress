import React, { useState, useEffect, useCallback } from 'react';

const ICONS = {
    success: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
    ),
    error: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>
    ),
    info: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
    ),
    warning: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
        </svg>
    ),
};

function ToastItem({ toast, onRemove }) {
    const [exiting, setExiting] = useState(false);

    useEffect(() => {
        const timer = setTimeout(() => {
            setExiting(true);
            setTimeout(() => onRemove(toast.id), 300);
        }, toast.duration || 3000);
        return () => clearTimeout(timer);
    }, [toast, onRemove]);

    const handleClose = () => {
        setExiting(true);
        setTimeout(() => onRemove(toast.id), 300);
    };

    return (
        <div className={`toast ${toast.type} ${exiting ? 'toast-exit' : ''}`}>
            <div className="toast-icon">{ICONS[toast.type] || ICONS.info}</div>
            <span className="toast-message">{toast.message}</span>
            <button className="toast-close" onClick={handleClose}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>
    );
}

// Global toast state
let toastListeners = [];
let toastId = 0;

export function addToast(message, type = 'info', duration = 3000) {
    const toast = { id: ++toastId, message, type, duration };
    toastListeners.forEach(fn => fn(toast));
}

export function ToastContainer() {
    const [toasts, setToasts] = useState([]);

    useEffect(() => {
        const listener = (toast) => {
            setToasts(prev => [...prev, toast]);
        };
        toastListeners.push(listener);
        return () => {
            toastListeners = toastListeners.filter(fn => fn !== listener);
        };
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    if (toasts.length === 0) return null;

    return (
        <div className="toast-container">
            {toasts.map(toast => (
                <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
            ))}
        </div>
    );
}

export default ToastContainer;

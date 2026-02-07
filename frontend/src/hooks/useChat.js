import { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../services/api';

export function useChat() {
    const [messages, setMessages] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [tokenCount, setTokenCount] = useState(0);
    const [ttlRemaining, setTtlRemaining] = useState(0);

    const abortControllerRef = useRef(null);
    const requestIdRef = useRef(0);

    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort();
        };
    }, []);

    const clearError = useCallback(() => setError(null), []);

    const stopGenerating = useCallback(() => {
        abortControllerRef.current?.abort();
        abortControllerRef.current = null;
        setIsLoading(false);
    }, []);

    const sendMessage = useCallback(async (text) => {
        if (!text.trim() || isLoading) return;

        abortControllerRef.current?.abort();
        const controller = new AbortController();
        abortControllerRef.current = controller;
        const reqId = ++requestIdRef.current;

        setIsLoading(true);
        setError(null);

        const userMessage = {
            id: `temp-${Date.now()}`,
            role: 'user',
            content: text,
            masked_content: '',
            timestamp: new Date().toISOString(),
        };

        setMessages(prev => [...prev, userMessage]);

        try {
            const response = await api.sendMessage(text, sessionId, controller.signal);

            if (reqId !== requestIdRef.current) return;
            abortControllerRef.current = null;

            const rawContent = response?.message?.content;
            const displayContent = (typeof rawContent === 'string' && rawContent.trim())
                ? rawContent.trim()
                : '(No response received)';

            const assistantMessage = {
                id: String(response?.message?.id ?? `msg-${Date.now()}`),
                role: 'assistant',
                content: displayContent,
                masked_content: response?.message?.masked_content ?? '',
                tokens_used: response?.message?.tokens_used ?? [],
                timestamp: response?.message?.timestamp ?? new Date().toISOString(),
            };

            setSessionId(response?.session_id ?? sessionId);
            setTokenCount(response?.token_count ?? 0);
            setTtlRemaining(response?.ttl_remaining ?? 0);
            setMessages(prev => {
                const updated = prev.map(msg =>
                    msg.id === userMessage.id
                        ? { ...msg, id: `user-${response?.message?.id ?? 'temp'}`, masked_content: text }
                        : msg
                );
                return [...updated, assistantMessage];
            });
        } catch (err) {
            if (reqId !== requestIdRef.current) return;
            if (err.name !== 'AbortError') {
                setError(err.message || 'Request failed');
                setMessages(prev => prev.filter(msg => msg.id !== userMessage.id));
            }
        } finally {
            if (reqId === requestIdRef.current) {
                setIsLoading(false);
            }
            abortControllerRef.current = null;
        }
    }, [sessionId, isLoading]);

    // Start a new chat
    const newChat = useCallback(() => {
        abortControllerRef.current?.abort();
        setMessages([]);
        setSessionId(null);
        setTokenCount(0);
        setTtlRemaining(0);
        setError(null);
        setIsLoading(false);
    }, []);

    const loadSession = useCallback(async (id) => {
        abortControllerRef.current?.abort();
        setIsLoading(true);
        setError(null);

        try {
            const session = await api.getSession(id);
            setSessionId(id);
            setMessages(session.messages || []);
            setTokenCount(session.token_count ?? 0);
            setTtlRemaining(session.ttl_remaining ?? 0);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Get masked prompt details for a message
    const getMaskedDetails = useCallback(async (messageId) => {
        if (!sessionId) return null;

        try {
            return await api.getMaskedPrompt(sessionId, messageId);
        } catch (err) {
            console.error('Failed to get masked details:', err);
            return null;
        }
    }, [sessionId]);

    return {
        messages,
        sessionId,
        isLoading,
        error,
        tokenCount,
        ttlRemaining,
        sendMessage,
        newChat,
        loadSession,
        getMaskedDetails,
        clearError,
        stopGenerating,
    };
}

export default useChat;

import { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../services/api';

export function useSessions() {
    const [sessions, setSessions] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    // Load sessions
    const loadSessions = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await api.listSessions();
            setSessions(response.sessions || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Create a new session
    const createSession = useCallback(async (title = null) => {
        try {
            const session = await api.createSession(title);
            setSessions(prev => [session, ...prev]);
            return session;
        } catch (err) {
            setError(err.message);
            return null;
        }
    }, []);

    // Delete a session
    const deleteSession = useCallback(async (id) => {
        try {
            await api.deleteSession(id);
            setSessions(prev => prev.filter(s => s.id !== id));
            return true;
        } catch (err) {
            setError(err.message);
            return false;
        }
    }, []);

    // Rename a session
    const renameSession = useCallback(async (id, title) => {
        try {
            await api.renameSession(id, title);
            setSessions(prev =>
                prev.map(s => s.id === id ? { ...s, title } : s)
            );
            return true;
        } catch (err) {
            setError(err.message);
            return false;
        }
    }, []);

    // Don't auto-load on mount — App.jsx triggers loadSessions after auth check
    // This avoids 401 errors for guest users

    // Group sessions by date — memoized to avoid re-computing every render
    const groupedSessions = useMemo(() => {
        const today = new Date();
        const todayStr = today.toDateString();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        const yesterdayStr = yesterday.toDateString();
        const lastWeekTs = today.getTime() - 7 * 86_400_000;

        return sessions.reduce((groups, session) => {
            const dateStr = new Date(session.created_at).toDateString();
            const dateTs = new Date(session.created_at).getTime();

            let group;
            if (dateStr === todayStr) {
                group = 'Today';
            } else if (dateStr === yesterdayStr) {
                group = 'Yesterday';
            } else if (dateTs > lastWeekTs) {
                group = 'Last 7 Days';
            } else {
                group = 'Older';
            }

            if (!groups[group]) groups[group] = [];
            groups[group].push(session);
            return groups;
        }, {});
    }, [sessions]);

    return {
        sessions,
        groupedSessions,
        isLoading,
        error,
        loadSessions,
        createSession,
        deleteSession,
        renameSession,
    };
}

export default useSessions;

import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { api } from '../services/api';

/**
 * Auth Context — provides user state, login, signup, logout across the app.
 * Tokens are stored in sessionStorage (cleared on tab close for security).
 * A draft input is preserved across login/signup redirects.
 */

const AuthContext = createContext(null);

// ── Token helpers (sessionStorage only — never localStorage) ──────

function getStoredTokens() {
    try {
        const access = sessionStorage.getItem('pf_access_token');
        const refresh = sessionStorage.getItem('pf_refresh_token');
        return { access, refresh };
    } catch {
        return { access: null, refresh: null };
    }
}

function storeTokens(access, refresh) {
    try {
        sessionStorage.setItem('pf_access_token', access);
        sessionStorage.setItem('pf_refresh_token', refresh);
    } catch { /* private browsing mode */ }
}

function clearTokens() {
    try {
        sessionStorage.removeItem('pf_access_token');
        sessionStorage.removeItem('pf_refresh_token');
    } catch { /* ignore */ }
}

// ── Draft helpers ──────────────────────────────────────────────────

export function getDraft() {
    try {
        return sessionStorage.getItem('pf_draft') || '';
    } catch {
        return '';
    }
}

export function saveDraft(text) {
    try {
        if (text.trim()) {
            sessionStorage.setItem('pf_draft', text);
        } else {
            sessionStorage.removeItem('pf_draft');
        }
    } catch { /* ignore */ }
}

export function clearDraft() {
    try {
        sessionStorage.removeItem('pf_draft');
    } catch { /* ignore */ }
}

// ── Provider ───────────────────────────────────────────────────────

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);         // { id, name, email }
    const [isLoading, setIsLoading] = useState(true); // true while checking token on mount
    const [error, setError] = useState(null);

    // On mount — try to restore session from stored token
    useEffect(() => {
        const init = async () => {
            const { access, refresh } = getStoredTokens();
            if (!access) {
                setIsLoading(false);
                return;
            }
            try {
                // Set token on api layer so the /me call includes it
                api.setAccessToken(access);
                const me = await api.getMe();
                setUser(me);
            } catch {
                // Token expired — try refresh
                if (refresh) {
                    try {
                        const res = await api.refreshToken(refresh);
                        storeTokens(res.access_token, res.refresh_token);
                        api.setAccessToken(res.access_token);
                        setUser(res.user);
                    } catch {
                        // Both tokens dead — clear
                        clearTokens();
                        api.setAccessToken(null);
                    }
                } else {
                    clearTokens();
                    api.setAccessToken(null);
                }
            } finally {
                setIsLoading(false);
            }
        };
        init();
    }, []);

    // ── Actions ─────────────────────────────

    const login = useCallback(async (email, password) => {
        setError(null);
        try {
            const res = await api.login(email, password);
            storeTokens(res.access_token, res.refresh_token);
            api.setAccessToken(res.access_token);
            setUser(res.user);
            return true;
        } catch (err) {
            setError(err.message || 'Login failed');
            return false;
        }
    }, []);

    const signup = useCallback(async (name, email, password) => {
        setError(null);
        try {
            const res = await api.register(name, email, password);
            storeTokens(res.access_token, res.refresh_token);
            api.setAccessToken(res.access_token);
            setUser(res.user);
            return true;
        } catch (err) {
            setError(err.message || 'Registration failed');
            return false;
        }
    }, []);

    const logout = useCallback(() => {
        clearTokens();
        api.setAccessToken(null);
        setUser(null);
    }, []);

    const clearAuthError = useCallback(() => setError(null), []);

    const refreshUser = useCallback(async () => {
        try {
            const me = await api.getMe();
            setUser(me);
        } catch { /* ignore */ }
    }, []);

    const value = {
        user,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        signup,
        logout,
        clearAuthError,
        refreshUser,
    };

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
}

export default useAuth;

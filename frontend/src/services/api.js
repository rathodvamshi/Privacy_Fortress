// ── Environment-aware API URL ─────────────────────────────────────
// In production (Vercel), uses VITE_API_URL env var; falls back to localhost for dev
const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/api';

// ── In-memory cache with TTL ──────────────────────────────────────
const _cache = new Map();
const DEFAULT_CACHE_TTL = 30_000; // 30 seconds

function cacheGet(key) {
  const entry = _cache.get(key);
  if (!entry) return undefined;
  if (Date.now() > entry.expires) {
    _cache.delete(key);
    return undefined;
  }
  return entry.data;
}

function cacheSet(key, data, ttl = DEFAULT_CACHE_TTL) {
  _cache.set(key, { data, expires: Date.now() + ttl });
}

function cacheInvalidate(prefix) {
  for (const key of _cache.keys()) {
    if (key.startsWith(prefix)) _cache.delete(key);
  }
}

function cacheClear() {
  _cache.clear();
}

// ── Request deduplication ─────────────────────────────────────────
const _inflight = new Map();

async function dedup(key, fetcher) {
  if (_inflight.has(key)) return _inflight.get(key);
  const promise = fetcher().finally(() => _inflight.delete(key));
  _inflight.set(key, promise);
  return promise;
}

// ── Internal token state ──────────────────────────────────────────
let _accessToken = null;

/**
 * Build headers — automatically attaches Bearer token when available.
 */
function authHeaders(extra = {}) {
  const headers = { 'Content-Type': 'application/json', ...extra };
  if (_accessToken) {
    headers['Authorization'] = `Bearer ${_accessToken}`;
  }
  return headers;
}

/**
 * Shared response handler — throws with backend detail on error.
 */
async function handleResponse(response) {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch { /* ignore parse errors */ }
    throw new Error(detail);
  }
  return response.json();
}

export const api = {
  // ── Token management ────────────────────────────────────────────
  setAccessToken(token) {
    _accessToken = token;
    // Clear cache when token changes (login/logout)
    cacheClear();
  },

  getAccessToken() {
    return _accessToken;
  },

  // ── Auth endpoints ──────────────────────────────────────────────
  async register(name, email, password) {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    return handleResponse(response);
  },

  async login(email, password) {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return handleResponse(response);
  },

  async refreshToken(refreshToken) {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return handleResponse(response);
  },

  async getMe() {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: authHeaders(),
    });
    return handleResponse(response);
  },

  // ── Chat endpoints ──────────────────────────────────────────────
  async sendMessage(message, sessionId = null, signal = undefined) {
    const controller = new AbortController();
    const timeoutMs = 90000;
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const onUserAbort = () => controller.abort();
    if (signal) {
      signal.addEventListener('abort', onUserAbort);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          message,
          session_id: sessionId,
        }),
        signal: controller.signal,
      });
      const data = await handleResponse(response);
      if (data?.message && typeof data.message.content !== 'string') {
        console.warn('[API] Chat response missing message.content');
      }
      // Invalidate session caches after new message
      cacheInvalidate('sessions:');
      if (data?.session_id) cacheInvalidate(`session:${data.session_id}`);
      return data;
    } finally {
      clearTimeout(timeoutId);
      if (signal) signal.removeEventListener('abort', onUserAbort);
    }
  },

  async maskText(text, sessionId = null) {
    const response = await fetch(`${API_BASE_URL}/mask`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        text,
        session_id: sessionId,
      }),
    });
    return handleResponse(response);
  },

  /**
   * Get masked prompt transparency data for the Masked Prompt Viewer.
   * Returns: original_message, masked_message, tokens[], ai_masked_response, ai_unmasked_response, encryption_status, ttl_remaining.
   */
  async getMaskedPrompt(sessionId, messageId) {
    const cacheKey = `masked:${sessionId}:${messageId}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    const response = await fetch(
      `${API_BASE_URL}/chat/${sessionId}/masked/${messageId}`,
      { headers: authHeaders() }
    );
    const data = await handleResponse(response);
    cacheSet(cacheKey, data, 120_000); // 2min cache
    return data;
  },

  // ── Session endpoints ───────────────────────────────────────────
  async listSessions() {
    const cached = cacheGet('sessions:list');
    if (cached) return cached;

    return dedup('sessions:list', async () => {
      const response = await fetch(`${API_BASE_URL}/sessions`, {
        headers: authHeaders(),
      });
      const data = await handleResponse(response);
      cacheSet('sessions:list', data, 15_000); // 15s cache
      return data;
    });
  },

  async getSession(sessionId) {
    const cacheKey = `session:${sessionId}`;
    const cached = cacheGet(cacheKey);
    if (cached) return cached;

    return dedup(cacheKey, async () => {
      const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        headers: authHeaders(),
      });
      const data = await handleResponse(response);
      cacheSet(cacheKey, data, 10_000); // 10s cache
      return data;
    });
  },

  async createSession(title = null) {
    const response = await fetch(`${API_BASE_URL}/sessions`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ title }),
    });
    const data = await handleResponse(response);
    cacheInvalidate('sessions:');
    return data;
  },

  async deleteSession(sessionId) {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    const data = await handleResponse(response);
    cacheInvalidate('sessions:');
    cacheInvalidate(`session:${sessionId}`);
    return data;
  },

  async renameSession(sessionId, title) {
    const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ title }),
    });
    const data = await handleResponse(response);
    cacheInvalidate('sessions:');
    cacheInvalidate(`session:${sessionId}`);
    return data;
  },

  // ── Profile endpoints ───────────────────────────────────────────
  async getProfile() {
    const cached = cacheGet('profile');
    if (cached) return cached;

    return dedup('profile', async () => {
      const response = await fetch(`${API_BASE_URL}/profile`, {
        headers: authHeaders(),
      });
      const data = await handleResponse(response);
      cacheSet('profile', data, 60_000); // 60s cache
      return data;
    });
  },

  async getPrivacyStats() {
    const cached = cacheGet('privacy:stats');
    if (cached) return cached;

    return dedup('privacy:stats', async () => {
      const response = await fetch(`${API_BASE_URL}/profile/stats`, {
        headers: authHeaders(),
      });
      const data = await handleResponse(response);
      cacheSet('privacy:stats', data, 30_000); // 30s cache
      return data;
    });
  },

  async updateProfile(data) {
    const response = await fetch(`${API_BASE_URL}/auth/profile`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    const result = await handleResponse(response);
    cacheInvalidate('profile');
    return result;
  },

  async changePassword(currentPassword, newPassword) {
    const response = await fetch(`${API_BASE_URL}/auth/change-password`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    return handleResponse(response);
  },

  async deleteAccount() {
    const response = await fetch(`${API_BASE_URL}/auth/account`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    return handleResponse(response);
  },

  // ── Health endpoint (public) ────────────────────────────────────
  async getHealth() {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const response = await fetch(`${baseUrl}/health`);
    return handleResponse(response);
  },

  async getSecurityStatus() {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const response = await fetch(`${baseUrl}/health/security`);
    return handleResponse(response);
  },
};

export default api;

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../hooks/useAuth.jsx';
import { api } from '../services/api';
import { addToast } from './Toast';

export function ProfilePage({ onClose }) {
    const { user, logout, refreshUser } = useAuth();

    const [profile, setProfile] = useState(null);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('overview');

    // Edit states
    const [editingName, setEditingName] = useState(false);
    const [newName, setNewName] = useState('');
    const [savingName, setSavingName] = useState(false);

    // Password change
    const [showPasswordForm, setShowPasswordForm] = useState(false);
    const [passwordData, setPasswordData] = useState({ current: '', newPass: '', confirm: '' });
    const [savingPassword, setSavingPassword] = useState(false);
    const [showPasswords, setShowPasswords] = useState({ current: false, new: false, confirm: false });

    // Delete account
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [deleteText, setDeleteText] = useState('');
    const [deleting, setDeleting] = useState(false);

    // Load profile data
    const loadProfile = useCallback(async () => {
        setLoading(true);
        try {
            const [profileData, statsData] = await Promise.all([
                api.getProfile(),
                api.getPrivacyStats(),
            ]);
            setProfile(profileData);
            setStats(statsData);
        } catch (err) {
            addToast('Failed to load profile', 'error');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { loadProfile(); }, [loadProfile]);

    useEffect(() => {
        if (user?.name) setNewName(user.name);
    }, [user]);

    // Close on Escape
    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose]);

    // ── Handlers ─────────────────────────────

    const handleSaveName = async () => {
        if (!newName.trim() || newName.trim() === user?.name) {
            setEditingName(false);
            return;
        }
        setSavingName(true);
        try {
            await api.updateProfile({ name: newName.trim() });
            addToast('Name updated successfully', 'success');
            setEditingName(false);
            await refreshUser();
            loadProfile();
        } catch (err) {
            addToast(err.message || 'Failed to update name', 'error');
        } finally {
            setSavingName(false);
        }
    };

    const handleChangePassword = async (e) => {
        e.preventDefault();
        if (passwordData.newPass !== passwordData.confirm) {
            addToast('New passwords do not match', 'error');
            return;
        }
        if (passwordData.newPass.length < 6) {
            addToast('Password must be at least 6 characters', 'error');
            return;
        }
        setSavingPassword(true);
        try {
            await api.changePassword(passwordData.current, passwordData.newPass);
            addToast('Password changed successfully', 'success');
            setShowPasswordForm(false);
            setPasswordData({ current: '', newPass: '', confirm: '' });
        } catch (err) {
            addToast(err.message || 'Failed to change password', 'error');
        } finally {
            setSavingPassword(false);
        }
    };

    const handleDeleteAccount = async () => {
        if (deleteText !== 'DELETE') return;
        setDeleting(true);
        try {
            await api.deleteAccount();
            addToast('Account deleted', 'info');
            logout();
            onClose();
        } catch (err) {
            addToast(err.message || 'Failed to delete account', 'error');
        } finally {
            setDeleting(false);
        }
    };

    // ── Computed ──────────────────────────────

    const userInitial = user?.name ? user.name.charAt(0).toUpperCase() : user?.email?.charAt(0).toUpperCase() || '?';
    const memberSince = profile?.member_since
        ? new Date(profile.member_since).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
        : '—';

    const fmt = (n) => {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return String(n || 0);
    };

    // ── Password field helper ────────────────

    const PassField = ({ label, field, placeholder, minLen }) => (
        <div className="pp-form-field">
            <label>{label}</label>
            <div className="pp-input-wrap">
                <input
                    type={showPasswords[field] ? 'text' : 'password'}
                    value={field === 'current' ? passwordData.current : field === 'new' ? passwordData.newPass : passwordData.confirm}
                    onChange={(e) => {
                        const key = field === 'current' ? 'current' : field === 'new' ? 'newPass' : 'confirm';
                        setPasswordData(p => ({ ...p, [key]: e.target.value }));
                    }}
                    required
                    minLength={minLen}
                    placeholder={placeholder}
                />
                <button type="button" className="pp-pass-toggle" onClick={() => setShowPasswords(s => ({ ...s, [field]: !s[field] }))}>
                    {showPasswords[field] ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                    ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    )}
                </button>
            </div>
        </div>
    );

    // ── Protection features data ─────────────

    const shields = [
        { icon: '🧠', name: 'Zero-Knowledge AI', desc: 'LLM never sees your real data', color: 'emerald' },
        { icon: '🔍', name: 'PII Auto-Detection', desc: 'NER + Regex + Fuzzy matching', color: 'blue' },
        { icon: '🔐', name: 'Encrypted Vault', desc: 'AES-256-GCM Redis storage', color: 'purple' },
        { icon: '⏱️', name: 'Auto-Expire', desc: '30-min TTL auto-delete', color: 'amber' },
        { icon: '🛡️', name: 'Prompt Shield', desc: 'Injection attack protection', color: 'emerald' },
        { icon: '🔒', name: 'Session Isolation', desc: 'Each chat independently secured', color: 'blue' },
    ];

    // ── Pipeline steps data ──────────────────

    const pipelineSteps = [
        { num: '1', name: 'Input Received', desc: 'Your message enters the system', icon: '📥' },
        { num: '2', name: 'PII Detection', desc: 'NER + Regex + Fuzzy engines scan for personal info', icon: '🔍' },
        { num: '3', name: 'Token Masking', desc: 'PII is replaced with anonymous tokens', icon: '🎭' },
        { num: '4', name: 'Encrypted Vault', desc: 'Mappings stored with AES-256-GCM in Redis', icon: '🔐' },
        { num: '5', name: 'AI Processes Safely', desc: 'LLM only sees masked text — zero knowledge', icon: '🤖' },
        { num: '6', name: 'Auto-Expire', desc: 'Vault mappings auto-delete after 30 minutes', icon: '⏱️' },
    ];

    // ── Render ───────────────────────────────

    if (loading) {
        return (
            <div className="pp-page">
                <div className="pp-loading">
                    <div className="pp-loading-ring"></div>
                    <p>Loading profile…</p>
                </div>
            </div>
        );
    }

    return (
        <div className="pp-page">
            {/* Scroll wrapper */}
            <div className="pp-scroll">
                <div className="pp-container">

                    {/* ───── Top bar ───── */}
                    <div className="pp-topbar">
                        <button className="pp-back" onClick={onClose}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="15 18 9 12 15 6"></polyline>
                            </svg>
                            Back to Chat
                        </button>
                    </div>

                    {/* ───── Hero card ───── */}
                    <div className="pp-hero">
                        {/* Animated gradient banner */}
                        <div className="pp-hero-banner">
                            <div className="pp-orb pp-orb-1"></div>
                            <div className="pp-orb pp-orb-2"></div>
                            <div className="pp-orb pp-orb-3"></div>
                        </div>

                        {/* Avatar + info */}
                        <div className="pp-hero-body">
                            <div className="pp-avatar-wrap">
                                <div className="pp-avatar-ring"></div>
                                <div className="pp-avatar">{userInitial}</div>
                            </div>

                            <div className="pp-hero-info">
                                {editingName ? (
                                    <div className="pp-name-edit">
                                        <input
                                            type="text"
                                            value={newName}
                                            onChange={(e) => setNewName(e.target.value)}
                                            className="pp-name-input"
                                            autoFocus
                                            maxLength={100}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') handleSaveName();
                                                if (e.key === 'Escape') { setEditingName(false); setNewName(user?.name || ''); }
                                            }}
                                        />
                                        <button className="pp-name-btn save" onClick={handleSaveName} disabled={savingName}>
                                            {savingName ? '…' : '✓'}
                                        </button>
                                        <button className="pp-name-btn cancel" onClick={() => { setEditingName(false); setNewName(user?.name || ''); }}>
                                            ✕
                                        </button>
                                    </div>
                                ) : (
                                    <h1 className="pp-hero-name">
                                        {user?.name || 'User'}
                                        <button className="pp-edit-btn" onClick={() => setEditingName(true)} title="Edit name">
                                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                                            </svg>
                                        </button>
                                    </h1>
                                )}
                                <p className="pp-hero-email">{user?.email}</p>
                                <div className="pp-hero-badges">
                                    <span className="pp-badge">
                                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                                        Joined {memberSince}
                                    </span>
                                    <span className="pp-badge accent">
                                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                                        Protected
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Stats strip */}
                        <div className="pp-stats-strip">
                            {[
                                { val: fmt(stats?.total_sessions), label: 'Sessions', color: 'blue' },
                                { val: fmt(stats?.total_messages), label: 'Messages', color: 'purple' },
                                { val: fmt(stats?.pii_detected), label: 'PII Masked', color: 'emerald' },
                                { val: `${(stats?.data_encrypted_kb || 0).toFixed(1)}`, label: 'KB Encrypted', color: 'amber' },
                            ].map((s, i) => (
                                <React.Fragment key={s.label}>
                                    {i > 0 && <div className="pp-stats-divider"></div>}
                                    <div className="pp-stat-item">
                                        <span className={`pp-stat-val ${s.color}`}>{s.val}</span>
                                        <span className="pp-stat-label">{s.label}</span>
                                    </div>
                                </React.Fragment>
                            ))}
                        </div>
                    </div>

                    {/* ───── Tabs ───── */}
                    <nav className="pp-tabs">
                        {[
                            { key: 'overview', label: 'Overview', icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg> },
                            { key: 'security', label: 'Security', icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg> },
                            { key: 'privacy', label: 'Privacy Stats', icon: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg> },
                        ].map(t => (
                            <button key={t.key} className={`pp-tab ${activeTab === t.key ? 'active' : ''}`} onClick={() => setActiveTab(t.key)}>
                                {t.icon}{t.label}
                            </button>
                        ))}
                    </nav>

                    {/* ───── Tab content ───── */}
                    <div className="pp-content">

                        {/* ── OVERVIEW ── */}
                        {activeTab === 'overview' && (
                            <div className="pp-panel" key="overview">
                                {/* Activity Summary */}
                                <div className="pp-card">
                                    <h3 className="pp-card-title">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                                        Activity Summary
                                    </h3>
                                    <div className="pp-activity-rows">
                                        <div className="pp-activity-row">
                                            <span>Tokens Generated</span>
                                            <span className="pp-activity-val">{fmt(stats?.tokens_generated)}</span>
                                        </div>
                                        <div className="pp-activity-row">
                                            <span>Avg PII per Session</span>
                                            <span className="pp-activity-val">{stats?.total_sessions ? Math.round((stats?.pii_detected || 0) / stats.total_sessions) : 0}</span>
                                        </div>
                                        <div className="pp-activity-row">
                                            <span>Encryption Standard</span>
                                            <span className="pp-activity-val accent">AES-256-GCM</span>
                                        </div>
                                        <div className="pp-activity-row">
                                            <span>Vault TTL</span>
                                            <span className="pp-activity-val">30 minutes</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Protection Features */}
                                <div className="pp-card">
                                    <h3 className="pp-card-title">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                                        Your Protection
                                    </h3>
                                    <div className="pp-shield-grid">
                                        {shields.map((s, i) => (
                                            <div className={`pp-shield-card ${s.color}`} key={i}>
                                                <span className="pp-shield-icon">{s.icon}</span>
                                                <div>
                                                    <div className="pp-shield-name">{s.name}</div>
                                                    <div className="pp-shield-desc">{s.desc}</div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* ── SECURITY ── */}
                        {activeTab === 'security' && (
                            <div className="pp-panel" key="security">
                                {/* Change Password */}
                                <div className="pp-card">
                                    <h3 className="pp-card-title">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path></svg>
                                        Change Password
                                    </h3>
                                    {!showPasswordForm ? (
                                        <div className="pp-sec-info">
                                            <p>Update your password to keep your account secure. We recommend using a strong, unique password.</p>
                                            <button className="pp-btn secondary" onClick={() => setShowPasswordForm(true)}>Change Password</button>
                                        </div>
                                    ) : (
                                        <form className="pp-pass-form" onSubmit={handleChangePassword}>
                                            <PassField label="Current Password" field="current" placeholder="Enter current password" />
                                            <PassField label="New Password" field="new" placeholder="At least 6 characters" minLen={6} />
                                            <PassField label="Confirm New Password" field="confirm" placeholder="Re-enter new password" minLen={6} />
                                            <div className="pp-form-actions">
                                                <button type="submit" className="pp-btn primary" disabled={savingPassword}>
                                                    {savingPassword ? 'Saving…' : 'Update Password'}
                                                </button>
                                                <button type="button" className="pp-btn ghost" onClick={() => { setShowPasswordForm(false); setPasswordData({ current: '', newPass: '', confirm: '' }); }}>
                                                    Cancel
                                                </button>
                                            </div>
                                        </form>
                                    )}
                                </div>

                                {/* Session Security */}
                                <div className="pp-card">
                                    <h3 className="pp-card-title">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
                                        Session Security
                                    </h3>
                                    <div className="pp-sec-info">
                                        <p>Your authentication tokens are stored in session storage and are cleared when you close the tab. Access tokens expire after 24 hours and refresh tokens after 30 days.</p>
                                        <div className="pp-sec-badges">
                                            {['Session-only tokens', 'bcrypt password hashing', 'JWT HS256 signed tokens'].map(b => (
                                                <span className="pp-sec-badge" key={b}>
                                                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                                                    {b}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                {/* Danger Zone */}
                                <div className="pp-card danger">
                                    <h3 className="pp-card-title danger">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                                        Danger Zone
                                    </h3>
                                    {!showDeleteConfirm ? (
                                        <div className="pp-sec-info">
                                            <p>Permanently delete your account and all associated data. This action cannot be undone.</p>
                                            <button className="pp-btn danger" onClick={() => setShowDeleteConfirm(true)}>Delete Account</button>
                                        </div>
                                    ) : (
                                        <div className="pp-delete-flow">
                                            <div className="pp-delete-warning">
                                                ⚠️ This will permanently delete your account, all chat sessions, and all associated data. Type <strong>DELETE</strong> to confirm.
                                            </div>
                                            <input
                                                type="text"
                                                value={deleteText}
                                                onChange={(e) => setDeleteText(e.target.value)}
                                                placeholder='Type "DELETE" to confirm'
                                                className="pp-delete-input"
                                                autoFocus
                                            />
                                            <div className="pp-form-actions">
                                                <button className="pp-btn danger" disabled={deleteText !== 'DELETE' || deleting} onClick={handleDeleteAccount}>
                                                    {deleting ? 'Deleting…' : 'Permanently Delete Account'}
                                                </button>
                                                <button className="pp-btn ghost" onClick={() => { setShowDeleteConfirm(false); setDeleteText(''); }}>Cancel</button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* ── PRIVACY ── */}
                        {activeTab === 'privacy' && (
                            <div className="pp-panel" key="privacy">
                                {/* PII Breakdown */}
                                <div className="pp-card">
                                    <h3 className="pp-card-title">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"></path><path d="M22 12A10 10 0 0 0 12 2v10z"></path></svg>
                                        PII Detection Breakdown
                                    </h3>
                                    <div className="pp-pii-list">
                                        {stats?.by_type && Object.entries(stats.by_type).map(([type, count]) => {
                                            const pct = Math.min(100, (count / Math.max(1, stats.pii_detected)) * 100);
                                            return (
                                                <div className="pp-pii-row" key={type}>
                                                    <div className="pp-pii-meta">
                                                        <span className={`pp-pii-dot ${type.toLowerCase()}`}></span>
                                                        <span className="pp-pii-type">{type}</span>
                                                    </div>
                                                    <div className="pp-pii-bar-track">
                                                        <div className={`pp-pii-bar-fill ${type.toLowerCase()}`} style={{ width: `${pct}%` }}></div>
                                                    </div>
                                                    <span className="pp-pii-count">{fmt(count)}</span>
                                                </div>
                                            );
                                        })}
                                        {(!stats?.by_type || Object.keys(stats.by_type).length === 0) && (
                                            <p className="pp-empty-text">No PII data detected yet. Start chatting to see your privacy stats.</p>
                                        )}
                                    </div>
                                </div>

                                {/* Pipeline */}
                                <div className="pp-card">
                                    <h3 className="pp-card-title">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                                        How Your Data Is Protected
                                    </h3>
                                    <div className="pp-pipeline">
                                        {pipelineSteps.map((step, i) => (
                                            <React.Fragment key={step.num}>
                                                <div className="pp-pipe-step">
                                                    <div className="pp-pipe-num">{step.icon}</div>
                                                    <div className="pp-pipe-body">
                                                        <div className="pp-pipe-name">{step.name}</div>
                                                        <div className="pp-pipe-desc">{step.desc}</div>
                                                    </div>
                                                </div>
                                                {i < pipelineSteps.length - 1 && <div className="pp-pipe-line"></div>}
                                            </React.Fragment>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default ProfilePage;

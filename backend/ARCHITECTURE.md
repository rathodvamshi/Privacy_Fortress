# Privacy Fortress — Two-Locker Architecture

**One-line for team/jury:**  
*"We use AES-256 to encrypt user identity, keep it outside the AI, and only resolve it at display time."*

**Core principle (do not break):**  
*Persistent encrypted profile recreates session state; sessions themselves are never stored with real data.*

---

## Quick reference

| Concept | Meaning |
|--------|--------|
| **Locker 1** | Ephemeral session vault (Redis, TTL). `[NAME_1] → Alice`. Wiped when session ends. |
| **Locker 2** | Persistent profile (MongoDB, AES-256). `{ name, college, email }`. One per user. Until "Forget me". |
| **Recreate** | On new session: load profile → decrypt in RAM → convert to mappings → seed ephemeral vault for this session. |
| **Never** | Store session vaults permanently; send PII to AI; log decrypted data. |

**Data flow in one sentence:** User text → mask (PII → placeholders) → AI sees only placeholders → response unmasked in RAM → user sees real values; persistent profile is one encrypted blob per user, used only to recreate session state.

---

## 1. Two Lockers (Critical Mental Model)

We have **two different lockers**. They serve different purposes. Do not merge them.

### Locker 1: Ephemeral Session Vault (SHORT-TERM)

| Aspect | Detail |
|--------|--------|
| **What it is** | Per-session, temporary. Exists only while chat is active. |
| **Stores** | `[NAME_1] → Alice Smith`, `[COLLEGE_1] → KMIT College` (placeholder → value) |
| **Lifetime** | Session ends → wiped. TTL expires → wiped. User logs out → wiped. |
| **Where** | Redis (or in-memory). Key: `pf:mappings:{session_id}` |
| **Why** | Fast placeholder replacement; context consistency inside one chat. |
| **Encryption** | Optional / defense-in-depth. Not meant for long-term memory. |

**This locker is NOT what you reopen later.** Do not expect it to exist in future sessions.

---

### Locker 2: Persistent Encrypted Profile Vault (LONG-TERM)

| Aspect | Detail |
|--------|--------|
| **What it is** | User-level, cross-session, cross-device. Permanent until user deletes. |
| **Stores** | **One** encrypted blob per user: `{ "name": "Alice Smith", "college": "KMIT College", "email": "..." }` |
| **Lifetime** | Days / months / years. Until user clicks **"Forget me"**. |
| **Where** | MongoDB `encrypted_profiles` collection. AES-256-GCM encrypted. |
| **Why** | Reuse user personal data in future sessions without AI ever learning it. |
| **Rule** | We do **not** store encrypted copies of every session. We store **one** user profile and **recreate** session state from it. |

**This locker survives across sessions.** AI cannot access it. Decrypted only in backend RAM when loading a session.

---

## 2. How Future Sessions Work (Correct Flow)

1. User logs in (same or new device).
2. Backend loads **encrypted profile** for `user_id` (if consent = true).
3. Decrypts it **in RAM**.
4. **Recreates a NEW session vault** for this session:
   - Converts profile `{ name, college, email }` → `[NAME_1] → …, [COLLEGE_1] → …, [EMAIL_1] → …`
   - Seeds the **ephemeral** vault for this `session_id` with these mappings.
5. Normal masking pipeline continues. AI still sees only placeholders.

**Do not** restore old session vaults. **Do not** store encrypted session vaults.  
**Do** store one encrypted user profile and recreate sessions from it.

---

## 3. User Consent (Mandatory)

Before storing anything in the **persistent** locker:

- Ask: `remember_me = true`, `sync_across_devices = true`.
- If consent is **false**: do **not** store profile; use only the ephemeral session vault.

---

## 4. Pipeline (Request Flow)

### Chat / Open session

```
1. Auth → user_id; get or create session_id.
2. Load ephemeral vault for this session_id (Redis).
3. If ephemeral empty AND user has consent AND has persistent profile:
   a. Load encrypted profile from MongoDB.
   b. Decrypt in RAM.
   c. Convert profile → session mappings ([NAME_1], [COLLEGE_1], …).
   d. Seed ephemeral vault for this session_id with these mappings (recreate session state).
   e. Load those mappings into pipeline.
4. Else if ephemeral has data: load ephemeral mappings into pipeline.
5. Mask user message; store updated mappings in ephemeral vault (TTL).
6. Send only MASKED content to LLM.
7. Unmask response in RAM; store masked only in DB; return unmasked to user.
```

### Saving to persistent profile

- User may **explicitly** set profile (e.g. name, college, email) via API.
- Or we **extract** from current session mappings (first USER → name, first COLLEGE → college, first EMAIL → email) and save that **one** profile object. We do **not** save raw session token mappings permanently.

---

## 5. AES-256 Usage

| Data | Where | Encrypted? | Notes |
|------|--------|------------|--------|
| Session mappings (ephemeral) | Redis | Optional (defense-in-depth) | TTL; wiped when session ends. |
| User profile (name, college, email) | MongoDB `encrypted_profiles` | Yes, AES-256-GCM | One blob per user. Until "Forget me". |
| Chat messages | MongoDB `messages` | N/A | **Masked only** — no real PII. |

---

## 6. API Endpoints

Base: `/api`. Auth: Bearer JWT where required.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/`, `/health`, `/health/security` | API info, health, security status |

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh` | Auth flow |
| GET | `/api/auth/me` | Current user |
| PUT | `/api/auth/profile` | Update name etc. |
| DELETE | `/api/auth/account` | Delete account and all user data |

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sessions` | List user sessions |
| POST | `/api/sessions` | Create session |
| GET | `/api/sessions/{session_id}` | Get session + messages (unmasked for display) |
| PUT | `/api/sessions/{session_id}` | Rename |
| DELETE | `/api/sessions/{session_id}` | Delete session + ephemeral vault for that session |

### Chat

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send message; mask → LLM → unmask → return |
| POST | `/api/chat/stream` | Streaming chat |
| GET | `/api/chat/{session_id}/masked/{message_id}` | Masked prompt details (transparency) |

### Vault (Consent + Persistent Profile + Forget me)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/vault/consent` | Get remember_me, sync_across_devices |
| PUT | `/api/vault/consent` | Update consent |
| GET | `/api/vault/profile` | Metadata only (has_profile, consent) |
| PUT | `/api/vault/profile` | Save profile: body `{ name?, college?, email? }` or `?session_id=...` to extract from session |
| DELETE | `/api/vault/profile` | **Forget me**: delete persistent profile + clear ephemeral vault for all user sessions |

---

## 7. Must Do / Never Do

### Must do

- AES-256 for **persistent** profile vault.
- Session-scoped placeholder mappings (ephemeral vault).
- Mask before AI; unmask only at display.
- Consent before persistence.
- "Forget me" deletes persistent profile and clears ephemeral vault for user.
- Backend-only decryption (RAM only).
- **One** encrypted user profile; recreate session state from it.

### Never do

- Store real PII in AI DB or send real PII to AI.
- Log decrypted data or store decrypted data on disk.
- Share vault access with AI.
- **Store encrypted copies of every session.** Store one profile only.
- Restore old session vaults; recreate from profile instead.

---

## 8. Simple Analogy

- **Big locker (persistent profile)** → "My name, my college" — kept until user says delete.
- **Small notebook (session vault)** → "Today's conversation only" — thrown away when session ends or TTL expires.

AI never opens either locker.

---

## 9. Final Direction

- This design is correct and intentional.
- Two lockers; do not simplify by merging them.
- Do not store session vaults permanently.
- Build exactly this model. If unclear, ask before changing.

---

## 10. Implementation checklist (for developers)

Use this to verify the codebase matches the architecture.

| Requirement | Where to check |
|-------------|-----------------|
| Ephemeral vault is per-session, TTL-based | `app/vault/redis_client.py`: key `pf:mappings:{session_id}`, `setex` with TTL |
| Persistent profile is one doc per user, AES-256 | `app/vault/profile_vault.py`: `store_profile` / `get_profile`; `app/vault/encryption.py` |
| Profile schema is `name`, `college`, `email` only | `app/vault/profile_vault.py`: `PROFILE_SCHEMA`, `normalize_profile` |
| Recreate session from profile when ephemeral empty | `app/routes/chat.py`, `app/routes/sessions.py`: load profile → `profile_to_session_mappings` → seed vault |
| Consent required before saving profile | `app/routes/vault.py`: PUT `/profile` checks `get_consent` |
| "Forget me" deletes profile + clears ephemeral for user | `app/routes/vault.py`: DELETE `/profile`; `profile_vault.delete_profile`; loop over user sessions, `redis_vault.delete_mappings`, `clear_pipeline` |
| No decrypted PII in logs | `app/vault/audit.py`: only hashes; no real values in `log_profile_save` / `log_profile_delete` |
| `has_profile` means document has `encrypted_blob` | `app/vault/profile_vault.py`: `has_profile` checks `encrypted_blob` presence |
| Mask before LLM; unmask only at display | `app/routes/chat.py`: `mask_result.masked_text` to Groq; `unmask_result.unmasked_text` to client |
| MongoDB stores masked content only in messages | `app/database/mongodb.py`: `add_message` takes `masked_content`; no PII in sessions collection |

See also `backend/DEVELOPER_CHECKLIST.md` for a concise pre-PR checklist.

---

## 11. Pro suggestions

- **Key management:** Keep `ENCRYPTION_KEY` in a secrets manager (e.g. 32-byte value); rotate with re-encryption if needed.
- **HTTPS:** Use TLS in production for all API traffic.
- **Per-user key derivation (optional):** For stronger isolation, derive a per-user key from master + `user_id` and use it only for that user’s encrypted profile.
- **Forget me is idempotent:** Safe to call multiple times; always delete profile and clear ephemeral vault for the user.
- **Rate limiting:** Keep existing limits on auth and chat; consider stricter limits on vault write endpoints.
- **Audit:** All vault actions (profile save, forget me) are logged with hashed identifiers only; never log decrypted content.

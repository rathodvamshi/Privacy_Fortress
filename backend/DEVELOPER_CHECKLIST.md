# Developer checklist — Privacy Fortress

Use this before opening a PR or demo. Ensures the two-locker model and security rules are intact.

---

## Two lockers (do not merge)

- [ ] **Locker 1 (ephemeral):** Session vault in Redis; key `pf:mappings:{session_id}`; TTL applied; never persisted beyond session/TTL.
- [ ] **Locker 2 (persistent):** One encrypted profile per user in `encrypted_profiles`; schema `{ name, college, email }`; stored only with consent; cleared only by "Forget me".

---

## Data flow

- [ ] User input is **masked** (PII → placeholders) before any call to the LLM.
- [ ] LLM receives and returns **only** masked text (e.g. `[NAME_1]`, `[COLLEGE_1]`).
- [ ] Unmasking happens **only in backend RAM**; unmasked content is sent to the client for display only.
- [ ] MongoDB `messages` store **only** `masked_content`; no real PII in message bodies.

---

## Persistent profile (Locker 2)

- [ ] Profile is saved only when user has **consent** (`remember_me` or `sync_across_devices`).
- [ ] Saving profile requires at least one of `name`, `college`, `email` (no all-empty overwrite).
- [ ] `has_profile` is true only when the document has an **encrypted_blob** (not just consent fields).
- [ ] On new session: if ephemeral vault is **empty** and user has consent and a profile, backend **recreates** session state from profile (decrypt → `profile_to_session_mappings` → seed ephemeral vault); we do **not** restore old session vaults.

---

## Security

- [ ] No **decrypted** PII in logs, metrics, or error messages.
- [ ] Audit events (e.g. profile save, forget me) use only **hashed** identifiers (e.g. `user_id_hash`); no real names/emails.
- [ ] Encryption key is from config/env; never hardcoded or committed.

---

## API

- [ ] `PUT /api/vault/profile`: requires consent; accepts body `{ name?, college?, email? }` and/or `?session_id=...`; rejects empty profile.
- [ ] `DELETE /api/vault/profile`: deletes persistent profile and clears ephemeral vault for **all** of the user’s sessions.
- [ ] Chat and session endpoints use **ephemeral-first** loading; profile is used only when ephemeral is empty and consent + profile exist.

---

## If you change vault or chat flow

- [ ] Re-read `ARCHITECTURE.md` (two lockers, recreate-from-profile, never store session vaults).
- [ ] Run through this checklist again after your changes.

---

**One-line to remember:**  
*Persistent encrypted profile recreates session state; sessions themselves are never stored with real data.*

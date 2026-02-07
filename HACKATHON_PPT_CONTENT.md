# Privacy Fortress — Hackathon Presentation (Full PPT Content)

**Use this as script + slide text.** Copy each "SLIDE" into one PowerPoint/Google Slide. Keep bullets short on slides; use "SPEAKER NOTES" while presenting.

---

## SLIDE 1 — Title

**Title:** Privacy Fortress  
**Subtitle:** Zero-Knowledge AI Chat — Your Identity Stays Yours

**Visual:** Clean lock/shield + chat bubble icon. Dark blue or deep purple background, white text.

**Speaker notes:**  
"Good [morning/afternoon]. We're [team name]. Our project is Privacy Fortress — an AI chat system where your name, college, and email never reach the AI. We use military-grade encryption and a two-locker architecture so that even we cannot see your data unless you're in the session. Today we'll walk you through the problem, why it matters in the real world, and how we built it."

---

## SLIDE 2 — The Real-World Problem

**Headline:** Why does this matter?

**Bullets (on slide):**
- **Healthcare:** Patient names in prompts can leak into LLM logs and training.
- **Education:** Student PII (name, college, roll numbers) sent to third-party AI.
- **Banking & HR:** Sensitive data in chat history becomes a compliance risk.
- **One breach = identity exposed** — once PII hits the model, you can't "undo" it.

**Visual:** Icons: hospital, graduation cap, bank, document with lock. Or a simple diagram: User → Chat → Cloud AI → "Where does my name go?"

**Speaker notes:**  
"In the real world, when you chat with an AI and say 'My name is Rahul from CBIT,' that text is often sent to the cloud, stored in logs, and sometimes used for training. In healthcare, that's a HIPAA problem. In education, it's FERPA. In India, it touches data localization and consent. We're not just protecting a name — we're protecting identity from ever entering the AI's memory. Once it's in the model, you cannot delete it. So the only safe approach is: never send it in the first place."

---

## SLIDE 3 — What Makes Us Different

**Headline:** How we're different from "just another AI chat"

**Bullets (on slide):**
- **Zero-knowledge AI:** The LLM never sees "Alice" or "KMIT" — only placeholders like `[NAME_1]`, `[COLLEGE_1]`.
- **Two-locker model:** Ephemeral session vault (wiped when you leave) + one encrypted profile per user (with your consent).
- **Recreate, don't restore:** We don't store every session; we store one encrypted profile and recreate context when you return.
- **AES-256-GCM:** All persistent PII is encrypted before it touches the database; decryption happens only in RAM, at display time.

**Visual:** Two lockers side by side — "Session vault (temporary)" and "Your profile (encrypted, one per user)." Or: User → [Mask] → AI sees [NAME_1] only.

**Speaker notes:**  
"Existing solutions often encrypt in transit or at rest but still send real PII to the model. We go further: the AI is blind to your identity. We use a two-locker design — a short-lived session vault for the current chat and a single encrypted profile per user that survives until you click 'Forget me.' We never store session vaults permanently; we store one profile and recreate session state from it. That's cleaner, safer, and easier to explain to regulators."

---

## SLIDE 4 — One Line for the Jury

**Headline:** One line to remember

**Single line on slide (large, centered):**  
*"We use AES-256 to encrypt user identity, keep it outside the AI, and only resolve it at display time."*

**Visual:** Minimal. Maybe a small lock icon + "AI" with a blindfold.

**Speaker notes:**  
"If you remember one thing from our pitch: we encrypt your identity, keep it out of the AI entirely, and only turn placeholders back into real values when we're rendering the response for you on the screen. The model never learns who you are."

---

## SLIDE 5 — Teamwork: Who Did What

**Headline:** Team & roles

**Bullets (customize names/roles):**
- **[Name]** — Architecture & backend: two-locker design, vault APIs, encryption pipeline.
- **[Name]** — PII detection & masking: NER (spaCy), regex, fuzzy matching, tokenizer.
- **[Name]** — Frontend & UX: chat UI, consent flows, "Forget me" and profile screens.
- **[Name]** — Integration & security: Auth (JWT), rate limiting, audit logging (no PII).
- **Together:** Problem framing, API design, and keeping "AI never sees PII" true end-to-end.

**Visual:** Simple role boxes or a small "idea → design → code → test" timeline with initials.

**Speaker notes:**  
"We split ownership clearly: [Name] drove the architecture and the vault; [Name] built the detection and masking pipeline; [Name] owned the frontend and user flows; [Name] handled auth and security. The key was aligning early on the principle that the AI must never see real identity — that constraint drove every technical decision."

---

## SLIDE 6 — System Flow (High Level)

**Headline:** End-to-end flow in one picture

**Visual:** Flow diagram (use icons or simple shapes):

1. **User** types: "I'm Alice from KMIT."
2. **Middleware** detects PII → replaces with `[NAME_1]`, `[COLLEGE_1]` → stores mapping in **ephemeral vault** (Redis, TTL).
3. **AI** receives only: "I'm [NAME_1] from [COLLEGE_1]."
4. **AI** replies with placeholders.
5. **Middleware** unmask in RAM → sends **User** the reply with "Alice" and "KMIT."
6. **DB** stores only masked messages; **persistent vault** (MongoDB) holds one encrypted profile per user (with consent).

**Bullets (short on slide):**
- User → Mask → Ephemeral vault (session)
- AI sees placeholders only
- Unmask in RAM → User sees real text
- One encrypted profile per user (Locker 2)

**Speaker notes:**  
"The user sends plain text. Our middleware runs NER, regex, and fuzzy matching to find names, colleges, emails, and replaces them with tokens. Those mappings live in an ephemeral vault for this session only. The LLM only ever sees placeholders. We unmask the response in memory and send the real text to the user. The database stores only masked content. If the user has consented, we keep one encrypted profile per user and use it only to recreate session state when they come back — we never store full session vaults."

---

## SLIDE 7 — Tech Stack & Key Decisions

**Headline:** Tech choices and why

**Bullets (on slide):**
- **Backend:** FastAPI — async, clear API contracts, easy to document (OpenAPI).
- **Detection:** spaCy NER + regex + RapidFuzz — balance of accuracy and speed for names, orgs, emails.
- **Ephemeral vault:** Redis with TTL — fast, session-scoped, auto-expiry (e.g. 30 min).
- **Persistent vault:** MongoDB `encrypted_profiles` — one document per user, AES-256-GCM blob.
- **LLM:** Groq (e.g. Llama) — we only send masked text; model choice is swappable.
- **Auth:** JWT (access + refresh) — stateless, works with consent and vault ownership.

**Visual:** Stack diagram: Frontend → API → Redis + MongoDB → LLM. Or a simple table: Component | Choice | Why.

**Speaker notes:**  
"We chose FastAPI for a clean, async backend and automatic API docs. For PII detection we combine spaCy's NER with regex and fuzzy matching so we catch names, colleges, and emails even with typos. Redis gives us a fast, TTL-based session vault; MongoDB holds the single encrypted profile per user. The LLM is behind our middleware — it only ever receives masked content, so we can swap the model later without changing the privacy model. JWT keeps auth simple and ties every request to a user for consent and vault access."

---

## SLIDE 8 — Two-Locker Architecture (Technical)

**Headline:** Two lockers — no merge

**Visual:** Two boxes:

**Locker 1 — Ephemeral**
- Per session, Redis, TTL
- Stores: `[NAME_1] → Alice`, `[COLLEGE_1] → KMIT`
- Wiped when session ends or TTL expires

**Locker 2 — Persistent**
- Per user, MongoDB, AES-256-GCM
- Stores: one blob `{ name, college, email }` (encrypted)
- Until user clicks "Forget me"
- Used only to **recreate** session state on next login

**Bullets (on slide):**
- Locker 1 = this chat only; Locker 2 = your identity, with consent.
- We never store session vaults permanently — we recreate from the one profile.

**Speaker notes:**  
"We have two distinct lockers. The first is ephemeral: it holds the placeholder-to-value mapping for the current session in Redis, with a TTL. When the session ends or the TTL expires, it's gone. The second is persistent: one encrypted profile per user in MongoDB, with consent. When you open a new session — even on another device — we load that profile, decrypt it in RAM, convert it to mappings, and seed the ephemeral vault for this session. We never save full session vaults; we only save one profile and recreate from it. That keeps the design simple and compliant."

---

## SLIDE 9 — Proof: Working Solution

**Headline:** It works — here's the proof

**Bullets (on slide):**
- **Live API:** `/api/chat` — send a message with your name/college; response is unmasked for you, stored masked in DB.
- **Vault API:** `GET/PUT /api/vault/consent`, `PUT /api/vault/profile`, `DELETE /api/vault/profile` (Forget me).
- **Security endpoint:** `/health/security` — shows encryption and vault status (no secrets).
- **Docs:** OpenAPI at `/docs` — try chat and vault flows with Bearer token.

**Visual:** Screenshot of Swagger UI with a sample request/response, or a short screen recording (30 sec): type "I am Alice from KMIT" → see unmasked reply; show DB has only `[NAME_1]` and `[COLLEGE_1]`.

**Speaker notes:**  
"You can try it now. Our API is running; we have OpenAPI docs at /docs. For chat, you send a message with your name and college — you get back a natural reply with your name in it, but the database and the LLM only ever see placeholders. We have vault endpoints for consent, saving your profile from the current session or from explicit fields, and Forget me, which deletes the persistent profile and clears the ephemeral vault. The health/security endpoint shows that encryption and vault are configured — without exposing keys. We're happy to do a quick live demo if time allows."

---

## SLIDE 10 — Real-World Example

**Headline:** Example: Student using the app

**Scenario (short on slide):**
1. **Day 1 — Laptop:** "I'm Priya from CBIT. I need tips for placements."  
   → AI sees `[NAME_1]` and `[COLLEGE_1]`; Priya sees her name and college in the reply.
2. **Priya opts in:** "Remember my details / Sync across devices."
3. **We save:** One encrypted profile `{ name: Priya, college: CBIT }` in Locker 2.
4. **Day 2 — Phone:** She logs in. We load profile → recreate mappings → new session works with "Priya" and "CBIT" without her typing them again.
5. **Later:** She clicks "Forget me" → profile and session vaults cleared; AI never learned her identity.

**Visual:** Simple timeline or 3–4 panels: Laptop → Cloud (encrypted) → Phone; then "Forget me" → lock icon with a cross.

**Speaker notes:**  
"Imagine Priya, a student. On day one she tells the chat she's Priya from CBIT and asks for placement tips. The AI only sees placeholders; she sees her name in the reply. She consents to remember and sync. We store one encrypted profile. Next day on her phone she logs in — we decrypt in RAM, recreate the mappings, and her new session already knows Priya and CBIT. If she clicks Forget me, we delete the profile and clear session data. The AI never had her real identity at any point."

---

## SLIDE 11 — Impact & Why It Matters

**Headline:** Impact

**Bullets (on slide):**
- **Privacy by design:** Identity never enters the model — no training on your PII, no log leaks.
- **Compliance-friendly:** Consent before persistence; explicit Forget me; audit logs without PII.
- **Cross-device without risk:** One encrypted profile; same experience on any device; AI still blind.
- **Trust:** Users can explain in one sentence: "The AI never sees my name; only placeholders."

**Visual:** Icons: shield, checklist, devices, handshake. Or a short quote: "My data stays mine."

**Speaker notes:**  
"The impact is threefold. First, privacy by design: the model never sees who you are, so there's nothing to leak or to train on. Second, we're built for compliance: consent before we store anything, a clear Forget me, and audit logs that never contain decrypted PII. Third, we enable cross-device use safely — one encrypted profile, recreated per session — without ever giving the AI your identity. That's the story we want users and enterprises to trust."

---

## SLIDE 12 — Future Scope

**Headline:** What's next

**Bullets (on slide):**
- **More entity types:** Phone, Aadhaar-like IDs, addresses — same pipeline, more token types.
- **Per-user key derivation:** Optional key per user for stronger isolation of encrypted profiles.
- **On-prem / air-gapped:** Same architecture; swap Redis/MongoDB for in-house stores.
- **Compliance packs:** Preset policies (e.g. education, healthcare) and audit exports for regulators.

**Visual:** Roadmap: Now → 6 months → 1 year. Or 4 small boxes with icons.

**Speaker notes:**  
"We're not stopping here. We can extend the same pipeline to more PII types — phone numbers, IDs, addresses — with the same zero-knowledge guarantee. We're considering per-user key derivation so each user's profile is encrypted with a key derived from a master and their ID. For enterprises, we can offer the same design on-prem or air-gapped. And we want to package compliance: presets for education or healthcare and audit exports that regulators can use without ever seeing real data."

---

## SLIDE 13 — Thank You & Q&A

**Headline:** Thank you

**Bullets (on slide):**
- **Privacy Fortress** — Zero-knowledge AI chat
- One line: *Encrypt identity; keep it outside the AI; resolve only at display time.*
- **Demo:** [URL or "Available at our booth"]
- **Questions?**

**Visual:** Same as title slide — logo, project name, contact or GitHub/demo link.

**Speaker notes:**  
"Thank you. Privacy Fortress is our take on zero-knowledge AI chat: we encrypt your identity, keep it out of the AI, and resolve it only when we show you the reply. We're happy to demo at the booth or answer any technical or compliance questions. Thank you."

---

## BONUS — Suggestions for the Jury

**Slide (optional, or use in Q&A):**
- **Why "two lockers"?** Separation of concerns: session state is temporary; long-term identity is consent-based and minimal.
- **Why not encrypt only in transit?** Then the provider and the model still see PII; we remove that by never sending it to the model.
- **Why one profile per user?** Simplicity and compliance: one place to encrypt, one place to delete (Forget me), no session vault sprawl.
- **Real-world analogy:** Like a bank locker (persistent) and a notepad (session) — notepad is destroyed; locker stays until you close it.

---

## How to Build This in PowerPoint / Google Slides

1. **One slide per section** — use the "Headline" as title and "Bullets (on slide)" as body. Keep 4–6 bullets per slide; avoid long paragraphs.
2. **Speaker notes** — paste the "Speaker notes" into the Notes pane so you can rehearse and stay on message.
3. **Visuals:**  
   - Use icons (e.g. Flaticon, thenounproject) for: lock, shield, chat, database, key.  
   - Use one main diagram for "System flow" and one for "Two lockers."  
   - Use a simple timeline or roadmap for "Future scope."
4. **Animations:**  
   - Title slide: title + subtitle fade in.  
   - Flow slide: arrows or steps appear one by one (e.g. "User → Mask → AI → Unmask → User").  
   - Two-locker slide: Locker 1 and Locker 2 appear in sequence.  
   - Keep animations subtle (e.g. Appear or Fade), not distracting.
5. **Design:**  
   - Consistent font (e.g. title 28–32 pt, body 18–22 pt).  
   - One dark accent (e.g. blue/purple) + white/light gray background.  
   - High contrast for accessibility.
6. **Timing:** Aim for ~1–1.5 minutes per slide (e.g. 12–15 slides ≈ 12–18 minutes); leave 3–5 minutes for Q&A.

---

## Image / Animation Suggestions (Quick Ref)

| Slide        | Suggestion |
|-------------|------------|
| 1 Title      | Lock + chat bubble; subtle gradient or dark background. |
| 2 Problem    | Icons: healthcare, education, bank; or "User → Cloud → ?" diagram. |
| 3 Different  | Two lockers side by side; or "AI" with blindfold. |
| 4 One line   | Small lock + "AI" icon; minimal. |
| 5 Team       | Role boxes or timeline with initials. |
| 6 System flow| 5–6 step flow with arrows (User → Mask → Vault → AI → Unmask → User). |
| 7 Tech stack | Stack diagram or table: Component | Tech | Why. |
| 8 Two lockers| Two boxes: "Ephemeral" and "Persistent" with 2–3 bullets each. |
| 9 Proof      | Screenshot of `/docs` or short demo clip. |
| 10 Example   | Timeline: Day 1 (laptop) → Consent → Day 2 (phone) → Forget me. |
| 11 Impact    | Shield, checklist, devices, handshake icons. |
| 12 Future    | Roadmap: Now → 6 mo → 1 yr. |
| 13 Thank you | Same as slide 1; add "Questions?" and demo link. |

Good luck at the hackathon.

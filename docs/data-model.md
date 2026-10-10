# Data Model — Ukinory

This document describes the core entities of Ukinory and how they relate to each other.

## Diagram

```mermaid
---
config:
  layout: elk
---
classDiagram
direction TB
  class User {
    email: string
    username: string
    passwordHash: string
    isGuest: boolean
    lastActiveAt: datetime
    isActive: boolean
    isStaff: boolean
  }

  class Invite {
    type: InviteType
    code: string
    status: InviteStatus
    expiresAt: datetime
    acceptedAt: datetime
  }

  class Movie {
    tmdbId: int
    wikidataId: string
    title: string
    releaseYear: int
    wikidataDescription: string
    runtime: int
    originalLanguage: string
    directors: string[]
    embedding: vector
    embeddingSourceHash: string
    embeddingTargetHash: string
    metadataFetchedAt: datetime
  }

  class Genre {
    wikidataId: string
    name: string
  }

  class EmbeddingBatchJob {
    jobName: string
    state: EmbeddingBatchJobState
    items: json
    finishedAt: datetime
    error: string
  }

  class Rating {
    title: string
    releaseYear: int
    rating: float
    liked: boolean
    watchedDate: date
  }

  class WatchlistEntry {
    title: string
    releaseYear: int
    addedDate: date
    source: WatchlistSource
  }

  class ProfileSummary {
    generatedAt: datetime
    metricsJson: json
    narrativeSummary: string
    language: string
  }

  class Session {
    sessionType: SessionType
    status: SessionStatus
    lastSeenAt: datetime
  }

  class ComparisonSession

  class Comparison {
    generationStatus: GenerationStatus
    generationStartedAt: datetime
    generatedAt: datetime
    inputsHash: string
    metricsJson: json
  }

  class ComparisonNarrative {
    inputsHash: string
    narrativeSummary: string
    individualSummaries: json
    recommendations: json
    modelVersion: string
  }

  class SwipeSession {
    type: SwipeSessionType
    status: SessionStatus
    lastSeenAt: datetime
  }

  class SwipeSessionCandidate {
    score: float
    position: int
  }

  class Swipe {
    action: SwipeActionType
  }

  class CandidateJustification {
    text: string
    modelVersion: string
  }

  class RatingPrediction {
    predictedRating: float
    confidence: float
    modelVersion: string
    generatedAt: datetime
  }

  class LegalDocument {
    type: LegalDocumentType
    version: string
    content: string
    effectiveAt: datetime
  }

  class UserLegalAcceptance {
    acceptedAt: datetime
  }

  class ImportJob {
    status: ImportJobStatus
    startedAt: datetime
    finishedAt: datetime
    result: json
    errorMessage: string
  }

  class ImportJobFile {
    filename: string
    content: binary
  }

  class ImportJobStatus {
    PENDING
    RUNNING
    SUCCEEDED
    FAILED
  }

  class WatchlistSource {
    IMPORTED
    SWIPE_ADDED
    SWIPE_MATCH
    COMPARISON_ADDED
  }

  class SessionType {
    SWIPE_SESSION
    COMPARISON_SESSION
  }

  class GenerationStatus {
    PENDING
    RUNNING
    READY
    NEEDS_DATA
    FAILED
  }

  class SwipeSessionType {
    INDIVIDUAL
    PAIRED
  }

  class SessionStatus {
    WAITING
    ACTIVE
    FINISHED
  }

  class EmbeddingBatchJobState {
    SUBMITTED
    SUCCEEDED
    FAILED
  }

  class SwipeActionType {
    SKIP
    WATCHLIST
  }

  class InviteType {
    COMPARISON
    PAIRED_SWIPE
  }

  class InviteStatus {
    PENDING
    ACCEPTED
    EXPIRED
  }

  class LegalDocumentType {
    TERMS
    PRIVACY
  }

  <<Enum>> WatchlistSource
  <<Enum>> SwipeSessionType
  <<Enum>> SessionStatus
  <<Enum>> SwipeActionType
  <<Enum>> InviteType
  <<Enum>> SessionType
  <<Enum>> GenerationStatus
  <<Enum>> InviteStatus
  <<Enum>> LegalDocumentType
  <<Enum>> EmbeddingBatchJobState
  <<Enum>> ImportJobStatus

  User "1" --> "0..*" Rating : has
  User "1" --> "0..*" WatchlistEntry : has
  User "1" --> "0..1" ProfileSummary : has current
  User "1" --> "0..*" RatingPrediction : receives
  User "1" --> "0..*" Invite : creates
  Invite "0..*" --> "0..1" User : accepted by
  Session "0..*" --> "0..*" User : includes
  Session <|-- ComparisonSession
  ComparisonSession "1" --> "0..1" Comparison : has
  Comparison "1" --> "0..*" ComparisonNarrative : narrated by
  Invite "0..*" --> "0..1" Session : for
  SwipeSession "0..*" --> "0..*" User : includes
  SwipeSession "1" --> "0..*" SwipeSessionCandidate : offers
  SwipeSessionCandidate "0..*" --> "1" Movie : for
  SwipeSessionCandidate "1" --> "0..1" CandidateJustification : justified by
  SwipeSessionCandidate "1" --> "0..*" Swipe : swiped in
  Swipe "0..*" --> "1" User : by
  Movie "0..*" --> "0..*" Genre : has
  Movie "0..1" --> "0..*" Rating : rated in
  Movie "0..1" --> "0..*" WatchlistEntry : appears in
  Movie "0..*" --> "0..1" EmbeddingBatchJob : embedded via
  Movie "1" --> "0..*" RatingPrediction : predicted for
  User "1" --> "0..*" UserLegalAcceptance : accepts
  LegalDocument "1" --> "0..*" UserLegalAcceptance : accepted via
  User "1" --> "0..*" ImportJob : starts
  ImportJob "1" --> "0..*" ImportJobFile : contains

```

## Entities

**User** — either a guest or a registered account, distinguished by `isGuest`. Every `User`, guest or registered, also has a `username`: guests get one auto-generated at creation (`guest_<random>`), which doubles as their login handle until they claim the account. Guests have `email`/`passwordHash` set to null and are created implicitly on first visit; registering (or "claiming" a guest session) simply fills in those fields on the same row and flips `isGuest` to `false`, so no other entity needs to know or care which kind of user it's dealing with. A DB-level check constraint enforces that only guests can have a null `email` — a registered `User` is never allowed to end up without one. `isActive`/`isStaff` are Django-auth boilerplate (account suspension, admin access) rather than product-level fields tied to any FR.

**Invite** — a shareable, expiring code that lets one user (guest or registered) bring another into a `ComparisonSession` or a `PAIRED` `SwipeSession`, without needing a public directory of users to search. `type` says what the invite is for. `session` (nullable FK to the common `Session` base) points at the room the invite opens: for comparison invites the room is created *together with* the invite in one transaction (`create_room`: room in `WAITING` + invite), so — unlike the original design — the target already exists at invite-creation time and is referenced directly. On acceptance, a handler registered per `type` runs; for comparisons it adds the acceptor to the room, flips it to `ACTIVE` and creates the `Comparison` (FR-B12). `acceptedAt` timestamps the acceptance; the acceptor is captured by the `accepted by` relation. Codes are random URL-safe strings (32 bytes), valid for 5 minutes, with at most 20 pending invites per inviter. **Gap:** `regenerate_invite` marks the previous invite `EXPIRED`, but `accept_invite` only rejects invites that are `ACCEPTED` or past `expiresAt`, so a superseded code keeps working until its own 5 minutes run out (while the room is still `WAITING`). Rejecting any `status != PENDING` in `accept_invite` would close it.

**Movie** — anchored on its `tmdbId` (the id TMDb's search returns during matching, FR-B15), but with its descriptive fields sourced from Wikidata rather than TMDb: `title`, `releaseYear`, `wikidataDescription`, `runtime`, `originalLanguage`, `directors`, and its `genres` (via the M2M below) are looked up from Wikidata using `tmdbId` as the join key (a Wikidata item declares its TMDb id via the `P4947` property) and cached once per `tmdbId`, so repeated references — across ratings, watchlist entries, swipes, matches, and predictions — never re-trigger a Wikidata lookup. A row is only created once **both** a TMDb match *and* a corresponding Wikidata item are found; a `tmdbId` with no matching Wikidata item stores nothing and is instead recorded as matched-but-without-metadata (FR-B19), not as an error. `embeddingSourceHash`/`embeddingTargetHash` are new: a hash of the fields the embedding was built from and a hash of the embedding pipeline/prompt version, so a re-import or a pipeline change can detect "does this row's embedding need regenerating?" without recomputing it speculatively.

**Genre** — a movie genre as classified by Wikidata (`wikidataId`, e.g. `Q471839` for Science Fiction), reused across every `Movie` that shares it rather than duplicated per movie.

**EmbeddingBatchJob** — a new entity tracking one submitted batch-embedding job (`jobName` is the id from the embedding provider's batch API). `state` moves from `SUBMITTED` to `SUCCEEDED`/`FAILED`; `items` records what was submitted in the batch and `error` captures the failure reason when `state = FAILED`. Every `Movie` embedded through the batch pipeline points back at the job that produced it, so a failed or still-pending job's movies are identifiable without re-scanning `embeddingSourceHash`. This formalizes FR-B22/FR-B25's embedding generation as an asynchronous, batched, and auditable step, rather than an inline synchronous call per movie.

**Rating** — a single Letterboxd entry connecting a user to a movie they've watched, sourced from `ratings.csv` and taking the watched date from `diary.csv` and checking whether it was liked or not from `liked/films.csv`. `title`/`releaseYear` are now stored directly on the row (shared with `WatchlistEntry` via a common abstract base), not just implied through `movie` — since `movie` is nullable (an unmatched or metadata-less title, FR-B19), the entry needs its own identity independent of whether the `Movie` link resolved. The uniqueness constraint is `(user, title, releaseYear)` accordingly, not `(user, movie)`.

**WatchlistEntry** — a movie a user wants to watch. Same `title`/`releaseYear` treatment and uniqueness rationale as `Rating` above. `source` distinguishes entries imported directly from `watchlist.csv` (`IMPORTED`), added through individual swiping (`SWIPE_ADDED`), added automatically because of a paired-session match (`SWIPE_MATCH`), or saved from a comparison result (`COMPARISON_ADDED`, new). The swipe-sourced ones need to be exported back out for re-import into Letterboxd; comparison-saved ones are exported through a comparison-scoped CSV.

**ProfileSummary** — the generated taste profile for a `User`: computed metrics plus the LLM-written narrative summary. Regenerated (and overwritten) each time a user re-imports an updated export.

**Session / ComparisonSession** — `Session` (in the `common` app) is the shared base for rooms: `sessionType`, `status` (`WAITING`/`ACTIVE`/`FINISHED`), `lastSeenAt` and a many-to-many `users`. `ComparisonSession` extends it with no extra columns and is the comparison "room", capped at 2 participants in application logic. `WAITING` = the creator is alone; `ACTIVE` = both joined and the comparison is being generated/shown; `FINISHED` = closed. `lastSeenAt` is a heartbeat refreshed whenever a member reads the room state; `close_stale_rooms` (2-minute window) deletes stale `WAITING` rooms (their invites go with them, via cascade) and marks stale `ACTIVE` ones `FINISHED`. Leaving a `WAITING` room removes the user (and deletes the room if empty); leaving an `ACTIVE` room whose comparison is `PENDING`/`NEEDS_DATA` deletes the `Comparison` and returns the room to `WAITING`; leaving in any other state (`RUNNING`/`READY`/`FAILED`) marks it `FINISHED`. The leaver is removed from `users`, so a finished comparison stays visible only to whoever remains.

**Comparison** — the result of comparing the two participants of a `ComparisonSession`, one-to-one with it (created when the second participant joins). It holds the generation lifecycle (`generationStatus`: `PENDING` → `RUNNING` → `READY`/`NEEDS_DATA`/`FAILED`; `generationStartedAt` lets a `RUNNING` row older than 2 minutes be treated as abandoned), `inputsHash` (SHA-256 over both users' ratings — title, year, rating, liked — so any change in either library is detected) and `metricsJson`. `metricsJson` is versioned (`METRICS_VERSION`) and split in two: `public` (compatibility score, taste similarity, library sizes, common films, overlap/Jaccard, rating gap/correlation, top-5 agreements and divergences) is what the API returns; `internal` (shared genres/directors, compact per-user profiles) only feeds the LLM prompt and is never returned (FR-B24 / FR-B27). Metrics are recomputed only when `inputsHash` or the version changes. `narrativeSummary` and `language` no longer live here — the narrative moved to `ComparisonNarrative` and `language` is gone entirely (see the FR-B43 gap). Participants are reached through the room (`session.users`), not directly.

**ComparisonNarrative** — the LLM output for one `Comparison` at one `inputsHash`: `narrativeSummary` (for the pair), `individualSummaries` (JSON, one text per participant keyed by user id, written in the third person without names because both participants see both), `recommendations` (JSON list of up to 5 joint recommendations: `movie_id`, title, year, genres, joint `score`, per-user fit, LLM `justification`, `fit_version`) and `modelVersion`. It works as a cache: while `inputsHash` matches (and the summaries exist and `fit_version` is current) it's reused with no new LLM call; when the libraries change, the new row replaces the old ones. It is only written when the LLM call succeeds — if the quota is exhausted or the provider fails, the result is returned with `narrative_available = false` and the recommendations are *not* persisted. Recommendations are stored as JSON rather than rows, so `movie_id` is a loose reference to `Movie` with no foreign key (a missing movie is skipped when resolved).

**SwipeSession** — a swipe session of either `INDIVIDUAL` type (one participant) or `PAIRED` type. `status` now tracks the session's lifecycle explicitly (defaulting to `WAITING`, e.g. for a paired session waiting on its second participant); `lastSeenAt` supports the real-time layer (FR-B38), tracking when the session was last active so stale/abandoned sessions can be identified. `users` is a plain many-to-many, with no `(session, user)` role or join-date captured — same "not worth a first-class entity yet" reasoning as the `Comparison`/`SwipeSession` participant tables below. **Note:** the direct `comparisonId` link to `Comparison` described in the original design is not present on the current model — a paired session's candidate pool is no longer necessarily seeded from a stored `Comparison` row (see the FR-B36 note under Design notes). `ComparisonSession` shares the `Session` base with the swipe sessions' `sessionType`/`status`/`lastSeenAt` vocabulary (`SessionType.SWIPE_SESSION` exists, and `Invite.session` points at the generic `Session`); this diagram still draws `SwipeSession` standalone because its model wasn't part of this revision.

**SwipeSessionCandidate** — new entity, and the biggest structural change in this revision: the candidate pool for a session, which used to be computed on the fly and never persisted (see the old FR-B31 note, "persists nothing new"), is now materialized as its own row per `(session, movie)` pair, with a `score` (the ranking signal used to build the pool) and a `position` (its fixed display order within the session, unique per session). Persisting the pool makes it stable across page refreshes/reconnects, gives `Swipe` and `CandidateJustification` something concrete to attach to instead of a loose `(session, movie)` pair, and means re-ranking logic only has to run once per session rather than on every request.

**Swipe** (renamed from `SwipeAction`) — a single swipe decision (skip or add to watchlist) by one participant, on a specific `SwipeSessionCandidate` rather than directly on a `Movie`. Since a `SwipeSessionCandidate` is already unique per `(session, movie)`, this is equivalent in what it can express to the old `(session, user, movie)` shape, but goes through the candidate row instead. Used to avoid re-showing the same candidate, to detect matches in paired sessions (see the FR-B39 design note below), and as training feedback for the ML re-ranking model.

**CandidateJustification** — the LLM-generated justification text shown alongside a candidate in a swipe session, closing the FR-B32/FR-B37 gap ("the generated text isn't stored anywhere"). It's now a strict one-to-one with `SwipeSessionCandidate` (rather than being tied to a `(SwipeSession, Movie)` pair as originally designed) — a natural fit now that the candidate itself is a stored row. For `PAIRED` sessions, it's still a single joint text shared by both participants rather than something duplicated per user, since it hangs off the shared `SwipeSessionCandidate`, not off either participant's `Swipe`. This makes it auditable/cacheable (same session won't re-prompt the LLM for a candidate it already justified). **Gap:** the current model only stores `text` and `modelVersion` — the `language` field called for by FR-B43 (recording which language a given justification was generated in) isn't present yet.

**RatingPrediction** — the output of the per-user ML rating-prediction model for a given movie: a predicted rating, which model version produced it, and when. Kept separate from `Rating` (actual Letterboxd ratings) so predicted and real data are never conflated.

**LegalDocument** — versioned content for the Terms and Conditions and the Privacy Policy (`type` distinguishes the two), closing the FR-B09 gap. Each edit to either document is a new row rather than an in-place update, so historical versions stay available for exactly the reason FR-B09 exists: knowing which text a given acceptance record refers to, even after the content is later revised.

**UserLegalAcceptance** — the record that a specific registered `User` accepted a specific `LegalDocument` version at a specific time, closing the FR-B08 gap. Created only at registration (or when claiming a guest account), never for guest sessions — matching FR-B08's requirement that guests see the documents non-blockingly rather than being forced to accept them. A guest who later claims their account produces the acceptance row at that point, same as any other registration.

**ImportJob** — tracks the asynchronous processing of a Letterboxd export uploaded by a `User`. `status` moves through `PENDING` → `RUNNING` → `SUCCEEDED`/`FAILED`; `startedAt`/`finishedAt` mark when processing began and ended, `result` holds the outcome of the import once it succeeds, and `errorMessage` captures the failure reason (truncated to 2000 characters) when it fails.

**ImportJobFile** — the uploaded export file(s) belonging to an `ImportJob`, stored as binary `content` alongside the original `filename`.

## Design notes

- **Surrogate `id` keys, plain `createdAt` audit timestamps, and stored foreign keys are all omitted from the class bodies.** Every entity is assumed to have a primary key, and every relationship shown as an arrow is assumed to be backed by whatever foreign key(s) implementing it requires (e.g. the `SwipeSession "1" --> "0..*" SwipeSessionCandidate` arrow implies a `sessionId` column on `SwipeSessionCandidate` at the physical level) — repeating that as an attribute on the class would just restate the arrow in text form. The one exception is `Swipe "0..*" --> "1" User : by`: unlike, say, `Rating` or `WatchlistEntry` (where the existing `User`/`Movie` arrows already say everything the old `userId`/`movieId` fields said), nothing else in the diagram captured *which* participant made a given swipe, so that arrow was added rather than just dropping the field with no trace of it. What's kept as an actual attribute is anything that's actually load-bearing for a requirement and isn't implied by any arrow: `User.lastActiveAt` (drives the FR-B10 cleanup job), `Invite.expiresAt` (drives FR-B13), `ProfileSummary/Comparison/RatingPrediction.generatedAt` (freshness/regeneration logic, e.g. FR-B04's re-import overwrite), `LegalDocument.effectiveAt` and `UserLegalAcceptance.acceptedAt` (FR-B09's versioning). `CandidateJustification` no longer lists a `generatedAt` — the current model relies on the inherited `createdAt` for that, same as any other entity, rather than a dedicated field. The rule of thumb: if a field either wouldn't break any FR by being removed, or is already implied by a drawn relation, it isn't in the diagram.

- **`User.isGuest`** is the entire guest/registered distinction — every other entity (`Rating`, `WatchlistEntry`, `Comparison`, `SwipeSession`, etc.) references a plain `User` id and behaves identically either way. This is what makes "claiming" an account a one-row update instead of a data migration.

- **`Invite`** decouples "how two people find each other" from what happens once they do — the same entity covers both comparisons and paired swipe sessions via `type`, and expiring unused invites (`status: EXPIRED`) keeps stale codes from being usable indefinitely. For comparisons the invite now points at an already-existing `WAITING` room (`session`), instead of the target being created only on acceptance. Short TTL (5 min), a cap of 20 pending invites per user, and a row lock on acceptance keep codes single-use and bounded.

- **`Movie.embedding`** is computed once per movie from its full set of stored fields (`title`, `wikidataDescription`, `genres`, `directors`, `originalLanguage`) rather than from `wikidataDescription` alone, and reused across all users — no per-user recalculation needed. `posterUrl`, `voteAverage`, and streaming-provider availability are fetched fresh from TMDb at display time rather than cached on `Movie`. `embeddingSourceHash`/`embeddingTargetHash` make that recomputation idempotent: if neither the source fields nor the embedding pipeline have changed since the last run, the movie is skipped rather than re-embedded.

- **Embedding generation is now an explicit batch pipeline (`EmbeddingBatchJob`), not an inline step.** Movies needing an embedding are grouped and submitted together to the embedding provider's batch API; each `Movie.embeddingBatch` points at the job that (will) produce its embedding, and the job's `state` is polled/updated until it resolves. This is a scaling change from the original design, where embedding generation wasn't modeled as its own entity at all — it matters for FR-B22 (seeded catalog) and FR-B25 (per-user watched-movie embeddings) alike, since both funnel through the same pipeline.

- **Movie metadata resolution happens in two decoupled steps.** FR-B15 resolves a TMDb match (search by title/year) for every imported or seeded title; only the subset whose `tmdbId` isn't already cached proceeds to FR-B16, where Wikidata metadata for *every outstanding `tmdbId` in that batch* is resolved together — one (or a handful of, for very large batches) SPARQL request instead of one request per movie.

- **`Rating`/`WatchlistEntry` can exist without a linked `Movie`.** A Letterboxd entry that TMDb can't match at all (FR-B15), or that matches a `tmdbId` with no Wikidata coverage (FR-B16), is still recorded — a user's watch history must never be silently dropped just because enrichment failed — just with `movieId` left null. This is also why `title`/`releaseYear` now live directly on `Rating`/`WatchlistEntry` (via a shared abstract base) rather than only being reachable through `movie`: without them stored on the row itself, an unmatched entry would have no stable identity at all, and the `(user, title, releaseYear)` uniqueness constraint wouldn't be expressible.

- **`SwipeSession.type`** unifies individual and paired swiping under one model, so the swipe/matching logic doesn't need two separate code paths. **`SwipeSession.status`** and **`SwipeSession.lastSeenAt`** are new: `status` gives the session an explicit lifecycle (e.g. `WAITING` for a paired session's second participant) instead of inferring it from participant count, and `lastSeenAt` gives the real-time layer (FR-B38) a way to tell an abandoned session from a live one.

- **Gap: the `SwipeSession → Comparison` link ("seeded by") from the original design isn't present on the current `SwipeSession` model.** FR-B36 calls for a paired session's candidate pool to be ranked using the combined compatibility logic from `Comparison`, but nothing on `SwipeSession` currently records which `Comparison` (if any) seeded it. Either that reuse happens without a stored reference (the pool is computed from the two users' data at session-creation time and then persisted onto `SwipeSessionCandidate`, with no ongoing link back to the `Comparison` row), or the wiring for FR-B36 is simply still pending — worth confirming with whoever owns the paired-session code.

- **Participants are now reached through `Session.users`, not through a `Comparison`–`User` association.** The many-to-many lives on the shared `Session` base (so on `ComparisonSession`), and `Comparison` hangs off the room one-to-one. At the relational level it's still a plain join table with no column beyond the two foreign keys (no joined-at, role or invited-by), so it stays an implementation detail of the diagram; if a participant-level attribute is ever needed it earns its own entity. The M2M is unbounded at the DB level — the 2-participant cap is enforced in `join_room_from_invite`, under a lock on the `Session` row so two simultaneous joiners can't both get in. `SwipeSession`'s participants follow the same "no cap in the schema" reasoning.

- **`SwipeSessionCandidate` is the standout structural change in this revision.** The original design treated a session's candidate pool as ephemeral — computed by a query, never stored (see the old FR-B31 note). The actual implementation persists it: one row per `(session, movie)`, carrying the `score` that ranked it and a `position` that fixes its display order, both enforced unique per session. This is what `Swipe` and `CandidateJustification` now attach to, instead of a loose `(session, movie)` pair — a session's candidate list becomes stable and independently queryable (e.g. "what did we already show this session") rather than something recomputed on every request.

- **`CandidateJustification`** is now a strict one-to-one with `SwipeSessionCandidate`, so a `PAIRED` session's joint justification is generated and stored once and read by both participants, and re-showing a candidate in the same session (e.g. after a page refresh) doesn't trigger a second LLM call — same intent as the original design, just attached to the candidate row instead of a `(sessionId, movieId)` pair now that one exists.

- **Match detection (FR-B39) is still a derived condition, not a stored entity — but now derived one level down.** A match is: within one `PAIRED` `SwipeSession`, does the same `SwipeSessionCandidate` have a `Swipe` row from each participant, both with `action = ADD_TO_WATCHLIST`? That's a query over `Swipe` (joined through `candidate`), checked whenever a swipe is recorded. When it's true, the backend inserts the two `WatchlistEntry` rows (`source: SWIPE_MATCH`) and pushes a transient real-time event to both clients (FR-B38) — but nothing about "the match" itself needs its own row, since `Swipe` + `SwipeSessionCandidate` already have everything needed to reconstruct it later (e.g. for FR-B07's data export, "matches" are just `WatchlistEntry` rows with `source = SWIPE_MATCH`).

- **`LegalDocument`** keeps versioned content independent of any single acceptance — the same version can be (and is meant to be) referenced by many `UserLegalAcceptance` rows, and a new version doesn't invalidate old acceptance records, it just means new registrations point at a newer `documentId`. This is now enforced at the code level, not just by convention: an existing `LegalDocument` row raises on `save()` if it's already persisted, so the only way to change published Terms/Privacy content is to create a new versioned row.

- **`User.lastActiveAt`** is updated on every authenticated request (alongside token validation) and is what the guest-cleanup job (FR-B10) checks — a guest `User` (and everything cascading from it: ratings, watchlist, profile, swipes, matches) is deleted once `lastActiveAt` falls outside the inactivity window. Registered users are exempt from this cleanup regardless of `lastActiveAt`.

- **A comparison's lifecycle is explicit, and its output is cached by input hash.** `Comparison.generationStatus` (`PENDING` → `RUNNING` → `READY`/`NEEDS_DATA`/`FAILED`) is moved under a row lock, so either participant's client can trigger generation without double-running it; `NEEDS_DATA` (a participant has no ratings) is a normal state, not a failure, and the client re-triggers when it changes. `inputsHash` makes regeneration idempotent in the same spirit as `Movie.embeddingSourceHash`: unchanged libraries mean no recomputation and no LLM call, changed ones replace the previous `ComparisonNarrative`.

- **`public` vs `internal` metrics are a privacy boundary, not just organisation.** Only `public` is serialized; `internal` (per-user favourites, mean ratings, shared genres/directors) is stored on the same JSON column but only ever passed to the LLM. Participants are labelled A/B in the prompt and the generated text must not name them, since each participant sees the other's summary. What each participant can see of the other is limited to: username, their ratings on films both rated, library size, and that summary.

- **Comparison rooms have a live layer, but it's not persisted.** `ComparisonSession.lastSeenAt` is the heartbeat (updated whenever a member reads the room state, which clients do by polling and on every socket message); the WebSocket per room only broadcasts "something changed" (`partner_joined`, `generation_started`, `generation_finished`) and clients re-fetch state. The socket authenticates through a JWT passed in the query string — necessary for browsers, though it can end up in server/proxy access logs.

- **Watchlist integration goes through the stored recommendations.** Saving a recommendation does a `get_or_create` on `(user, title, releaseYear)` with `source = COMPARISON_ADDED` (and back-fills `movie` if an existing entry lacked it); the recommendation has to be one of the room's current ones. Two things to be aware of: removing one deletes *any* matching entry for that user regardless of `source` (so it would also delete an `IMPORTED` Letterboxd entry), and because recommendations are only persisted when the LLM call succeeds, saving/exporting returns "not ready" for a comparison whose narrative failed.

- **Gap: deleting a user doesn't delete their comparisons.** Account deletion removes the user's membership rows, but `ComparisonSession`, `Comparison` and `ComparisonNarrative` survive for the remaining participant, still containing the deleted user's ratings on shared films (inside `metricsJson`) and their taste summary. Worth deciding whether FR-B06/B10 should delete rooms/comparisons the user took part in, or scrub their entries.

- **Gap: `language` is no longer modelled for comparisons.** The old `Comparison.language` field is gone and `ComparisonNarrative` doesn't have one; the narrative generation reviewed takes no language parameter and the prompt is English. FR-B43 therefore isn't covered for comparison narratives yet, same as the `CandidateJustification` gap.

- **Behaviour in the code with no FR yet.** The existing requirements are left untouched, so a few implemented behaviours aren't traced to any: the comparison room lifecycle (creation with the invite, 2-participant cap, leaving, stale-room cleanup), the generation status/retry flow, saving comparison recommendations to the watchlist plus their CSV export, and the comparison WebSocket. They're documented in the entities and notes above; FR-B11/B12/B13, FR-B28–B30 and FR-B38 are the closest existing anchors.

## Traceability Matrix

Maps each backend functional requirement to the entities it touches. Frontend requirements (FR-F) are omitted — they consume these same entities through the API rather than modifying the model directly. Business rules (RN-01/02/03) are intentionally left out for now.

| Requirement | Involved UML entities | Relevant attributes/relations | Relation type | Notes |
|---|---|---|---|---|
| FR-B01: Immediate use as a guest | User | isGuest, lastActiveAt, username | Direct | Creates the row without email/passwordHash; `username` is now auto-generated for guests rather than left implicit (`id` is assumed, not explicitly modeled) |
| FR-B02: Register with email/password | User | email, passwordHash, isGuest | Direct | — |
| FR-B03: Login → session token | User | email, passwordHash | Direct | The JWT itself isn't a persisted entity (stateless) |
| FR-B04: Claim guest session | User | email, passwordHash, isGuest | Direct | Update of the same row, not a data migration |
| FR-B04 (continued): keep history when claiming | Rating, WatchlistEntry, ProfileSummary, Swipe | Preserved via each entity's relation to `User` (not a stored FK column); past "matches" are kept as `WatchlistEntry` rows with `source = SWIPE_MATCH`, not as their own entity | Indirect | No change needed since the `User`'s `id` doesn't change. Entity renamed from `SwipeAction` to `Swipe` |
| FR-B05: Validate token on every request | User | lastActiveAt | Direct | Updated on every authenticated call |
| FR-B06: Logout and account/data deletion | User + every entity related to it (Rating, WatchlistEntry, ProfileSummary, Swipe, RatingPrediction, UserLegalAcceptance) + `Invite` (as inviter or acceptor) + the room participant join tables (`Session.users` for comparison rooms, the swipe-session equivalent) | Cascading delete via each entity's relation to `User` | Direct | `UserLegalAcceptance` added to the cascade, now that it exists. `SwipeAction` renamed to `Swipe` **Gap:** `ComparisonSession`/`Comparison`/`ComparisonNarrative` aren't deleted with the user — only the participant link and the user's `Invite` rows go — so the other participant keeps a result that still embeds the deleted user's ratings on shared films and taste summary (see Design notes) |
| FR-B07: Export all data (JSON) | User, Rating, WatchlistEntry, ProfileSummary, Swipe, RatingPrediction, UserLegalAcceptance | Aggregated via each entity's relation to `User` | Indirect | Aggregated read via the `User` relation, creates no new entity; the user's "matches" are read as a subset of their `WatchlistEntry` rows **Open:** it isn't clear from the code reviewed whether comparison results (`Comparison`/`ComparisonNarrative`) the user took part in are included in the export |
| FR-B08: Terms/Privacy acceptance at registration | LegalDocument, UserLegalAcceptance | acceptedAt (the accepting user and the accepted document are captured by relations, not stored fields) | Direct | A `UserLegalAcceptance` row is created at registration (or when claiming a guest account). No row is created for guest sessions: the documents are only shown non-blockingly |
| FR-B09: Versioned Terms/Privacy content | LegalDocument | type, version, content, effectiveAt | Direct | Every edit to the text creates a new row/version instead of overwriting — now enforced by the model itself, which raises on any update to an existing row; `UserLegalAcceptance`'s relation to `LegalDocument` fixes which version each user accepted |
| FR-B10: Automatic deletion of inactive guests | User | isGuest, lastActiveAt | Direct | Cleanup job; cascade same as FR-B06 |
| FR-B11: Generate invite link | Invite, User, Session | type, code, status, expiresAt, session | Direct | The creator is captured by the `User "1" --> "0..*" Invite : creates` relation, not a stored field. For comparison invites a `ComparisonSession` (`WAITING`) is created in the same transaction and referenced through `Invite.session`. |
| FR-B12: Accept invite link | Invite, Session, ComparisonSession, Comparison | status, acceptedAt, session | Direct | The acceptor is captured by the `Invite "0..*" --> "0..1" User : accepted by` relation. Runs under a row lock on the invite; for comparisons it adds the acceptor to the room's `users`, sets the room `ACTIVE` and creates the `Comparison` (`PENDING`). Rejects own, already-accepted and expired invites, and full/closed rooms. **Gap:** an invite superseded by `regenerate_invite` (status `EXPIRED`) can still be accepted until its `expiresAt` — see the `Invite` entity note |
| FR-B13: Expire unused invites | Invite | status = EXPIRED, expiresAt | Direct | Two paths: the scheduled `expire_stale_invites` job flips overdue `PENDING` invites to `EXPIRED`, and `regenerate_invite` expires a room's earlier pending invites. Acceptance also checks `expiresAt` itself, so the job is housekeeping rather than the enforcement point |
| FR-B14: Import Letterboxd export | Rating, WatchlistEntry | title, releaseYear (now stored on the row itself, not only implied via `movie`); source (WatchlistEntry); rating/liked/watchedDate (Rating) | Direct | Ownership by the importing user is captured by each entity's relation to `User`, not a stored field |
| FR-B15: Match to a TMDb movie | Movie | tmdbId | Direct | Only resolves the `tmdbId`; the row itself is created in FR-B16, once Wikidata metadata for that id is also found |
| FR-B16: Fetch descriptive metadata (from Wikidata) | Movie, Genre | title, releaseYear, wikidataDescription, runtime, originalLanguage, directors, genres | Direct | Creates the row; a `tmdbId` with no matching Wikidata item creates nothing (see FR-B19). `posterUrl`/`voteAverage`/`streamingProviders` are not part of this — they're fetched live from TMDb at display time instead. Field renamed `description` → `wikidataDescription` |
| FR-B17: Handle TMDb/Wikidata rate limits | — | — | Not applicable | External API access logic (TMDb search and Wikidata SPARQL alike), not data |
| FR-B18: Cache resolved metadata | Movie | the whole row acts as the cache, keyed by `tmdbId` | Direct | Every not-yet-cached `tmdbId` from an import is resolved together in one batched Wikidata request rather than one per movie |
| FR-B19: Controlled ingestion errors | — | — | Not applicable | Error handling, not persistence. TMDb-side failures are mapped to a controlled response; Wikidata-side failures during the batched metadata step are not yet mapped the same way — an open gap |
| FR-B20: Seed the catalog from TMDb | Movie | bulk creation independent of any user | Direct | — |
| FR-B21: Exclude adult/unrated/low-vote titles | — | `include_adult=false`, `vote_count.gte=N` as parameters of the TMDb discover-endpoint call | Not applicable | No longer an attribute gap: the filter is applied when requesting the data from TMDb (FR-B20), `voteCount`/`adult` aren't stored on `Movie` or filtered after the fact. Doesn't apply to movies arriving via user import (FR-B15), which must never be filtered |
| FR-B22: Embeddings for seeded movies | Movie, EmbeddingBatchJob | embedding, embeddingSourceHash, embeddingTargetHash, embeddingBatch | Direct | Now goes through an explicit batch job entity instead of an inline call; `state` on the job tracks the async result |
| FR-B23: Periodic catalog refresh | Movie | new/updated rows | Direct | — |
| FR-B24: Internal quantitative profile metrics | ProfileSummary | metricsJson | Direct | — |
| FR-B25: Embeddings of the user's watched movies | Movie, Rating | embedding (Movie), joined via Rating | Indirect | Reuses the already-computed `Movie.embedding` (built from the movie's full stored metadata, not just `wikidataDescription`); adds no attribute of its own |
| FR-B26: LLM-generated profile narrative | ProfileSummary | narrativeSummary | Direct | — |
| FR-B27: Expose only the narrative | ProfileSummary | narrativeSummary (metricsJson omitted) | Direct | — |
| FR-B28: Overlap/divergence metrics | Comparison, Rating, Movie | metricsJson (`public` / `internal`), inputsHash | Direct / Indirect | Computed from both users' `Rating` rows (genres/directors via `Movie`) and their taste embeddings; exactly two participants. Recomputed only when `inputsHash` or `METRICS_VERSION` changes. Only `public` is returned by the API |
| FR-B29: LLM-based joint recommendations | ComparisonNarrative, Comparison | narrativeSummary, individualSummaries, recommendations, modelVersion, inputsHash | Direct | Replaces the old `Comparison.narrativeSummary`. Candidates come from the joint-profile pool (films neither participant has rated); the LLM writes the pair narrative, per-person summaries and per-recommendation justifications. Cached per `inputsHash`, older rows are deleted, and nothing is stored if the LLM call fails |
| FR-B30: Expose comparison result | Comparison, ComparisonNarrative, ComparisonSession, User, Movie | generationStatus, metricsJson.public, narrative fields, session users | Direct | Members only. Enriched at request time with TMDb poster/id (not stored) and participant usernames. Also served per room, only once `generationStatus = READY`, where each recommendation also gets an `in_watchlist` flag. A user's comparisons are listed through their room membership |
| FR-B31: Candidate pool (individual) | Movie, Rating, WatchlistEntry, SwipeSessionCandidate | embedding, exclusion of watched/already-swiped titles; score, position | Indirect / Direct | Ranking is still computed by combining several entities via a query, but the resulting pool is now persisted as `SwipeSessionCandidate` rows instead of nothing |
| FR-B32: Per-candidate justification (LLM) | CandidateJustification | text, modelVersion | Direct | The generated text used to not be stored anywhere; now it's persisted one-to-one with `SwipeSessionCandidate`, auditable and cacheable. **Gap:** `language` is called for by FR-B43 but isn't a field on the current model |
| FR-B33: Record swipe action | Swipe | action | Direct | Renamed from `SwipeAction`. Session and movie are now reached indirectly through `candidate` (`SwipeSessionCandidate`) rather than a direct `Movie`/`SwipeSession` relation; actor is still captured directly (`User : by`) |
| FR-B34: Watchlist CSV for re-import | WatchlistEntry | source IN (SWIPE_ADDED, SWIPE_MATCH) | Direct | — A comparison-scoped CSV export also exists; it exports the room's recommended films the user has saved, regardless of `source` |
| FR-B35: Start a paired swipe session | SwipeSession, User | type = PAIRED, status, unbounded M2M relation to User | Direct | The `"1..2"` cardinality from the original design isn't DB-enforced on the current `users` M2M; capping participants at two, if still required, happens in application logic |
| FR-B36: Shared pool from compatibility | SwipeSession, Comparison | the `seeded by` relation to Comparison | Direct | **Gap:** this relation isn't present on the current `SwipeSession` model — worth confirming whether FR-B36's reuse of `Comparison` data still happens, and if so, how it's wired without a stored reference The `Comparison` now lives on a `ComparisonSession` (room); there is still no link from `SwipeSession` |
| FR-B37: Joint per-candidate justification | CandidateJustification | text | Direct | Same entity as FR-B32; now related to a `SwipeSessionCandidate` (not a `SwipeSession`+`Movie` pair), so one row still serves as the joint justification for both participants. The `PAIRED` aspect comes from the candidate's session's `type` |
| FR-B38: Real-time connection per session | SwipeSession, Swipe | the session's (assumed) id is used as the room; `lastSeenAt` tracks session liveness; `Swipe` is what gets broadcast | Direct (partial) | The connection itself isn't a persisted entity; each incoming `Swipe` is broadcast to the other participant, and that broadcast is where the match check happens Comparison rooms also have their own real-time channel (not specific to paired swipe) |
| FR-B39: Match detection | Swipe, SwipeSessionCandidate, WatchlistEntry | action | Indirect | A match is a derived condition (two `Swipe` rows on the same `SwipeSessionCandidate`, both with `action = ADD_TO_WATCHLIST`), not its own entity; when detected, two `WatchlistEntry` rows are inserted (`source = SWIPE_MATCH`) |
| FR-B40: Per-user prediction model | RatingPrediction, Rating, Movie | predictedRating, embedding | Direct / Indirect | Direct on the output (`RatingPrediction`), indirect on the training data; user and movie are captured by relations |
| FR-B41: Cross-user collaborative filtering | RatingPrediction, Rating | every `Rating` row on the platform | Direct / Indirect | Same as FR-B40, but with platform-wide scope |
| FR-B42: Expose predictions | RatingPrediction | predictedRating, modelVersion | Direct | — |
| FR-B43: Language preference for LLM content | ProfileSummary, Comparison, CandidateJustification | narrativeSummary, language | Direct (partial) | The requested language is a request parameter; it's meant to be recorded per justification via `CandidateJustification.language`, but that field is currently missing from the model — see the gap noted under FR-B32 **Gap (comparison):** `Comparison.language` was removed and `ComparisonNarrative` has no `language` field; the narrative generation reviewed takes no language parameter and its prompt is English, so FR-B43 isn't implemented for comparison narratives yet |
| FR-B44: Structured error format | — | — | Not applicable | Error handling, not data |
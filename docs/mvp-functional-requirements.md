# Functional Requirements — Ukinory (MVP)

## Backend

### Authentication (registered or guest)
- **FR-B01**: Allow a user to use the app immediately as a guest, without registering, with no email or password involved.
- **FR-B02**: Allow a user to register with an email and password.
- **FR-B03**: Allow a user to log in and receive a session token (JWT).
- **FR-B04**: Allow a guest to "claim" their session by registering — converting their existing guest data into a permanent account under the same identity, with nothing lost.
- **FR-B05**: Validate the session token (guest or registered) on every authenticated request and associate all data with that user's id, regardless of guest/registered status.
- **FR-B06**: Allow a user to log out, and to delete their account (or guest session) and all associated data.

### Data rights & legal compliance
- **FR-B07**: Allow a user (registered or guest) to export all of their stored account data as a downloadable JSON file. This is distinct from the Letterboxd-specific watchlist CSV export (FR-B34), which is a re-import format rather than a full account export.
- **FR-B08**: Require explicit acceptance of the Terms and Conditions and Privacy Policy at registration. For guest sessions, surface the same documents non-blockingly rather than forcing acceptance.
- **FR-B09**: Serve versioned Terms and Conditions and Privacy Policy content, so a record of which version a registered user accepted can be kept.
- **FR-B10**: Automatically delete a guest account and all of its associated data after a set period of inactivity (e.g. 7 days since the last authenticated request), via a scheduled cleanup job — so abandoned guest sessions don't accumulate indefinitely.

### Cross-user connections (invite links)
- **FR-B11**: Allow a user to generate a shareable invite link/code for starting a comparison or a paired swipe session.
- **FR-B12**: Allow another user to accept an invite link, linking their profile to the requested comparison or paired session.
- **FR-B13**: Expire unused invite links after a set period.

### Data ingestion (Letterboxd export + TMDb)
- **FR-B14**: Accept an uploaded Letterboxd export (zip or individual CSVs) and parse it into structured records, tied to the current user (guest or registered).
- **FR-B15**: Match each Letterboxd entry to a TMDb movie using title and release year, handling ambiguous or unmatched titles.
- **FR-B16**: Fetch full metadata for each matched movie from TMDb.
- **FR-B17**: Handle TMDb API rate limits.
- **FR-B18**: Cache already-downloaded TMDb metadata to avoid unnecessary API calls.
- **FR-B19**: Return clear, handled errors (malformed CSV, unmatched titles, TMDb failures).

### Movie catalog seeding (candidate pool)
- **FR-B20**: Periodically ingest a baseline catalog of movies directly from TMDb's own discovery endpoints so unwatched candidates exist for recommendations even before enough users have imported their own history.
- **FR-B21**: Exclude adult, unrated, or extremely low-vote-count titles from the seeded catalog to keep candidate quality high.
- **FR-B22**: Generate embeddings for seeded movies at ingestion time, using the same pipeline as imported movies, so they're immediately usable for similarity-based candidate ranking.
- **FR-B23**: Refresh the seeded catalog on a recurring schedule to pick up newly released and newly popular titles.

### Profile generation
- **FR-B24**: Compute quantitative taste metrics per user as an internal input for the narrative profile below. These metrics are never exposed to the user as their own standalone statistics/charts (see design note under Known Constraints).
- **FR-B25**: Generate embeddings for the synopses of a user's watched movies.
- **FR-B26**: Generate a qualitative, narrative taste profile via LLM reasoning over the computed metrics and embeddings.
- **FR-B27**: Expose the resulting profile (narrative summary only) through the API — the underlying metrics from FR-B24 are used to generate it but are not returned as standalone statistics.

### Compatibility comparison
- **FR-B28**: Compute overlap and divergence metrics across two or more users linked via an accepted invite.
- **FR-B29**: Generate LLM-based joint recommendations justified by the combined profiles.
- **FR-B30**: Expose the comparison result (metrics + narrative + joint recommendations) through the API.

### Swipe recommendation engine — individual mode
- **FR-B31**: Build a candidate pool of unwatched movies for a user, drawn from both the seeded catalog (FR-B20) and movies logged by other users, filtered/ranked by similarity to their taste profile via embeddings/vector search.
- **FR-B32**: Generate a short, personalized justification per candidate via LLM, referencing the user's actual rating history.
- **FR-B33**: Record each swipe action (skip / add to watchlist) per user and movie.
- **FR-B34**: Generate a Letterboxd-importable CSV containing the movies added to the watchlist via swiping.

### Swipe recommendation engine — paired mode
- **FR-B35**: Allow two users, linked via an accepted invite, to start a paired swipe session.
- **FR-B36**: Build a shared candidate pool for a paired session, ranked using the combined compatibility logic from FR-B28/B29 rather than a single profile.
- **FR-B37**: Generate a joint justification per candidate explaining why it suits both participants.
- **FR-B38**: Establish a real-time connection per paired session so both participants' swipe actions are visible to each other live.
- **FR-B39**: Detect a "match" when both participants swipe "add to watchlist" on the same movie, and add that movie to both users' watchlists automatically.

### Machine learning module
- **FR-B40**: Train a per-user rating-prediction model using that user's own ratings, to predict scores for unwatched candidates.
- **FR-B41**: Train a cross-user collaborative-filtering model over all ratings across the platform (guest and registered alike) to strengthen recommendations as overall usage grows.
- **FR-B42**: Expose predicted ratings and model confidence through the API for use in the profile and swipe views.

### Localization & error handling
- **FR-B43**: Accept a language preference (Spanish or English) on requests that generate LLM content (profile narrative, comparison narrative, swipe justifications) and produce that content in the requested language.
- **FR-B44**: Return a consistent, structured error response format for errors.

## Frontend
- **FR-F01**: Registration and login screens — registration includes a required checkbox to accept the Terms and Conditions and Privacy Policy (FR-B08).
- **FR-F02**: Account claim screen — turn a guest session into a registered account without losing existing progress.
- **FR-F03**: Letterboxd import screen — upload form for the export, with feedback on parsing/matching progress and results.
- **FR-F04**: Profile screen — the LLM-generated narrative summary and ML-predicted ratings for notable unwatched candidates. Deliberately does **not** include a stats-dashboard layout (no genre/decade breakdown charts, most-watched cast/crew lists, or highest/lowest-rated lists) to avoid resembling Letterboxd Pro/Patron's paid stats pages.
- **FR-F05**: Invite creation screen — generate and share an invite link for starting a comparison or a paired swipe session.
- **FR-F06**: Invite acceptance screen — opens as a guest session automatically if the visitor isn't logged in, so accepting an invite never requires signing up first.
- **FR-F07**: Comparison screen — overlap metrics, divergences, and joint recommendations for the linked users, with an option to start a paired swipe session from the result.
- **FR-F08**: Swipe screen (individual mode) — card showing poster, title, year, genres, synopsis, streaming availability, and the reason for the recommendation, with actions to skip, add to watchlist, or open the movie on Letterboxd.
- **FR-F09**: Swipe screen (paired mode) — same card UI, plus real-time match notifications.
- **FR-F10**: Watchlist export screen — review accumulated swipe-adds (individual and matched) and download them as a Letterboxd-importable CSV.
- **FR-F11**: Account management screen — for registered users, view/delete account and export all account data as JSON (FR-B07); for guests, shows the "claim account" prompt in place of account settings, plus the same scoped delete/export options for the guest session.
- **FR-F12**: Terms and Conditions screen.
- **FR-F13**: Privacy Policy screen — explains what data is collected and why, and provides direct account-deletion and data-export controls (or links to the Account management screen's actions).
- **FR-F14**: Loading and error states — visible across all views.
- **FR-F15**: 404 screen for unknown routes.
- **FR-F16**: 500 / fallback screen shown when the backend is unreachable or returns an unexpected error.
- **FR-F17**: Language switcher screen element — Spanish/English, applied across the UI, including LLM-generated content requested from the backend.
- **FR-F18**: About/Credits screen — displays the required TMDb attribution (the mandated notice text and approved logo), as required by TMDb's API Terms of Use, regardless of whether the app is monetized.

### Global layout & responsiveness
- **FR-F19**: Persistent navigation bar — links to the relevant screens depending on auth state (guest vs. registered), plus the language switcher (FR-F17).
- **FR-F20**: Footer — links to the Terms and Conditions (FR-F12) and Privacy Policy (FR-F13) screens, plus a link to the About/Credits screen (FR-F18).
- **FR-F21**: Responsive layout across all screens.

## Known constraints

- **Letterboxd has no usable API for this project, in either direction.** Their public API is invite-only, and they are not currently granting access for data-analysis, recommendation, or LLM-related projects — meaning even a formal request would likely be denied for a project like this one. Scraping is also explicitly against their terms of use. The only compliant path is the one already designed: the user manually exports their own data via Letterboxd's official account-settings export feature and uploads it themselves (FR-B14 / FR-F03) — this relies on Letterboxd's own sanctioned export tool, not on API access or scraping, and stays limited to the user's own data. This also means Ukinory can never push data back into a user's Letterboxd account automatically; the CSV export/import step (FR-B34 / FR-F10) will always be a manual round trip.
- **Letterboxd's terms also prohibit recreating features exclusive to their paid accounts, "through our API or another means."** Checked in detail: Letterboxd Pro/Patron's paid stats specifically cover genre/decade breakdowns, most-watched actors/directors, and highest/lowest-rated film lists — computed from a user's own watch history. Ukinory's Profile feature was redesigned to avoid this overlap: the equivalent metrics (FR-B24) are computed only as an internal input for the LLM-generated narrative and are never exposed to the user as their own statistics or charts (FR-B27 / FR-F04). Nothing else in Ukinory (compatibility comparison, swipe/matching, ML predictions for *unwatched* films) has an equivalent in Letterboxd's paid tiers.
- **Guest sessions have no recovery path.** Losing the browser/device (or clearing storage) before claiming an account means that guest's data is permanently unreachable — there is no email or credential to recover it by. This is an accepted trade-off for letting strangers try the app without asking them to trust it with a signup first. This does not remove their right to export or delete data while the session is still reachable (FR-B07 / FR-F13) — it only means that right becomes moot once the token is lost, or once the inactivity-based cleanup (FR-B10) removes the data automatically first.
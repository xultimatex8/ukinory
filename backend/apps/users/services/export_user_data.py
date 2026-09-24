from django.utils import timezone


def _iso(value):
    return value.isoformat() if value else None


def _serialize_swipe_session(session, session_reference):
    return {
        "session_reference": session_reference,
        "type": session.type,
        "status": session.status,
        "created_at": _iso(getattr(session, "created_at", None)),
        "last_seen_at": _iso(session.last_seen_at),
    }


def _serialize_swipe(swipe, session_reference_by_pk):
    candidate = swipe.candidate
    movie = candidate.movie if candidate else None
    session_pk = candidate.session_id if candidate else None

    return {
        "action": swipe.action,
        "movie_title": movie.title if movie else None,
        "movie_tmdb_id": movie.tmdb_id if movie else None,
        "session_reference": session_reference_by_pk.get(session_pk),
        "created_at": _iso(getattr(swipe, "created_at", None)),
    }


def _serialize_rating(rating):
    return {
        "title": rating.title,
        "release_year": rating.release_year,
        "rating": rating.rating,
        "liked": rating.liked,
        "watched_date": _iso(rating.watched_date),
        "matched_movie_tmdb_id": rating.movie.tmdb_id if rating.movie_id else None,
    }


def _serialize_watchlist_entry(entry):
    return {
        "title": entry.title,
        "release_year": entry.release_year,
        "added_date": _iso(entry.added_date),
        "source": entry.source,
        "matched_movie_tmdb_id": entry.movie.tmdb_id if entry.movie_id else None,
    }


def _serialize_legal_acceptance(acceptance):
    document = acceptance.document

    return {
        "document_type": document.type,
        "document_version": document.version,
        "accepted_at": _iso(acceptance.accepted_at),
    }


def export_user_data(user):
    swipe_sessions = list(user.swipe_sessions.all())
    session_reference_by_pk = {s.pk: i + 1 for i, s in enumerate(swipe_sessions)}

    swipes = user.swipes.select_related("candidate", "candidate__movie", "candidate__session")

    return {
        "exported_at": timezone.now().isoformat(),
        "account": {
            "email": user.email,
            "username": user.username,
            "is_guest": user.is_guest,
            "created_at": _iso(getattr(user, "created_at", None)),
            "last_active_at": _iso(user.last_active_at),
        },
        "ratings": [
            _serialize_rating(r) for r in user.ratings.select_related("movie").all()
        ],
        "watchlist": [
            _serialize_watchlist_entry(w) for w in user.watchlist_entries.select_related("movie").all()
        ],
        "swipe_sessions": [
            _serialize_swipe_session(s, session_reference_by_pk[s.pk]) for s in swipe_sessions
        ],
        "swipes": [_serialize_swipe(s, session_reference_by_pk) for s in swipes],
        "legal_acceptances": [
            _serialize_legal_acceptance(a) for a in user.legal_acceptances.select_related("document").all()
        ],
    }

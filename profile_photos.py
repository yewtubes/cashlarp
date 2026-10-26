"""Persist the original client's cropped profile photos in local SQLite."""
import base64
import binascii
import hashlib
import re


def photo_url(store, uid):
    with store.connect() as db:
        row = db.execute("SELECT mime_type,digest FROM profile_photos WHERE user_id=?", (uid,)).fetchone()
    if not row:
        return ""
    extension = "png" if row["mime_type"] == "image/png" else "jpg"
    return "/local-profile-photo/" + uid + "/" + row["digest"] + "." + extension


def save(store, uid, encoded, mime_type):
    from server import APIError
    if not isinstance(encoded, str) or len(encoded) > 4_000_000:
        raise APIError(400, "Choose a PNG or JPEG profile photo under 3 MB")
    if encoded.startswith("data:"):
        match = re.fullmatch(r"data:image/(?:png|jpeg);base64,(.+)", encoded, re.S)
        if not match:
            raise APIError(400, "Choose a PNG or JPEG profile photo")
        encoded = match[1]
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise APIError(400, "Invalid profile photo encoding")
    # The native canvas always exports JPEG, including when the source is PNG.
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        actual_mime = "image/png"
    elif image.startswith(b"\xff\xd8\xff"):
        actual_mime = "image/jpeg"
    else:
        raise APIError(400, "Choose a PNG or JPEG profile photo")
    if len(image) > 3_000_000 or mime_type not in ("image/png", "image/jpeg"):
        raise APIError(400, "Choose a PNG or JPEG profile photo under 3 MB")
    digest = hashlib.sha256(image).hexdigest()[:16]
    with store.connect() as db:
        db.execute("INSERT INTO profile_photos VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET mime_type=excluded.mime_type,digest=excluded.digest,image=excluded.image", (uid, actual_mime, digest, image))
    return photo_url(store, uid)

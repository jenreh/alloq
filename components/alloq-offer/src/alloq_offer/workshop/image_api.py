"""HTTP route for the pictures of image chapters.

Offers are readable by every signed-in user, so a valid session is enough. A blob
is only served when a live image chapter of the offer shows it, and only as PNG
or JPEG; everything else answers 404 so blob ids cannot be probed.
"""

from typing import Final

from fastapi import APIRouter, Depends, HTTPException, Response, status

from alloq_offer.workshop.services import images
from appkit_commons.database.session import get_asyncdb_session
from appkit_user.authentication.http_guard import require_session

OFFERS_PREFIX: Final = "/api/offers/"
IMAGES_INFIX: Final = "/images/"
IMAGE_ROUTE: Final = OFFERS_PREFIX + "{offer_id}" + IMAGES_INFIX + "{blob_id}"
CSP: Final = "default-src 'none'; sandbox"
# A blob id never changes its bytes (one blob per SHA-256).
CACHE_CONTROL: Final = "private, max-age=3600"

router = APIRouter(dependencies=[Depends(require_session)])


def image_path(offer_id: int, blob_id: int) -> str:
    return IMAGE_ROUTE.format(offer_id=offer_id, blob_id=blob_id)


@router.get(IMAGE_ROUTE)
async def offer_image(offer_id: int, blob_id: int) -> Response:
    found = await images.offer_image(get_asyncdb_session, offer_id, blob_id)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    data, mime = found
    return Response(
        content=data,
        media_type=mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": CSP,
            "Cache-Control": CACHE_CONTROL,
        },
    )

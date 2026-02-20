import json
import logging
import os

from django.conf import settings
from pywebpush import webpush, WebPushException

from tasks.models import PushSubscription

logger = logging.getLogger(__name__)


def _vapid_private_key():
    # Prefer PEM file if it exists next to manage.py
    pem_path = os.path.join(settings.BASE_DIR, 'private_key.pem')
    if os.path.exists(pem_path):
        return pem_path
    # Fall back to raw base64url string from settings
    return getattr(settings, "VAPID_PRIVATE_KEY", "")


def send_push_notification(user_list, title, body, url=None, tag=None):
    if not getattr(settings, "PUSH_NOTIFICATIONS_ENABLED", False):
        logger.debug("Push notifications disabled, skipping.")
        return

    private_key = _vapid_private_key()
    vapid_claims_email = getattr(settings, "VAPID_CLAIMS_EMAIL", "")
    if not private_key or not vapid_claims_email:
        logger.warning("VAPID private key or claims email not configured.")
        return

    user_ids = [u.pk for u in user_list]
    if not user_ids:
        return

    subscriptions = list(PushSubscription.objects.filter(user_id__in=user_ids))
    if not subscriptions:
        logger.debug("No push subscriptions found for users: %s", user_ids)
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "",
        "tag": tag or "",
    })

    vapid_claims = {"sub": vapid_claims_email}

    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=vapid_claims,
            )
            logger.info("Push sent to %s (%s)", sub.user.username, sub.endpoint[:50])
        except WebPushException as e:
            response = getattr(e, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in (404, 410):
                sub.delete()
                logger.info("Deleted expired push subscription %s", sub.endpoint)
            else:
                logger.warning("Push failed (HTTP %s) for %s: %s", status_code, sub.endpoint[:50], e)
        except Exception as e:
            logger.warning("Push error for %s: %s", sub.endpoint[:50], e)

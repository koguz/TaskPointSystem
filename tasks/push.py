import json
import logging

from django.conf import settings
from pywebpush import webpush, WebPushException

from tasks.models import PushSubscription

logger = logging.getLogger(__name__)


def send_push_notification(user_list, title, body, url=None, tag=None):
    if not getattr(settings, "PUSH_NOTIFICATIONS_ENABLED", False):
        return

    vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    vapid_claims_email = getattr(settings, "VAPID_CLAIMS_EMAIL", "")
    if not vapid_private_key or not vapid_claims_email:
        return

    user_ids = [u.pk for u in user_list]
    subscriptions = PushSubscription.objects.filter(user_id__in=user_ids)

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
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
        except WebPushException as e:
            status_code = getattr(e, "response", None)
            if status_code is not None:
                status_code = getattr(e.response, "status_code", None)
            if status_code in (404, 410):
                sub.delete()
                logger.info("Deleted expired push subscription %s", sub.endpoint)
            else:
                logger.warning("Push notification failed for %s: %s", sub.endpoint, e)
        except Exception as e:
            logger.warning("Push notification error for %s: %s", sub.endpoint, e)

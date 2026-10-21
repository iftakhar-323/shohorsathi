from celery import shared_task


@shared_task(name="city.user.deleted")
def user_deleted(payload):
    from .privacy import forget

    forget(payload["user_id"])

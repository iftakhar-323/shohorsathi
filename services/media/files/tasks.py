from celery import shared_task


@shared_task(name="media.user.deleted")
def user_deleted(payload):
    from .models import MediaFile
    from .views import delete_files

    return delete_files(MediaFile.objects.filter(owner_user_id=payload["user_id"]))

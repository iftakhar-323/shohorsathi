from shohor_common.privacy import DELETED_NAME

from .models import Conversation, Message


def forget(user_id):
    """The other side keeps the conversation; this person's words and name are removed."""
    Message.objects.filter(sender_user_id=user_id).update(body="[deleted]", attachment_url="", sender_name=DELETED_NAME)
    Conversation.objects.filter(customer_user_id=user_id).update(customer_name=DELETED_NAME)
    Conversation.objects.filter(provider_user_id=user_id).update(provider_name=DELETED_NAME)

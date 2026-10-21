from django.urls import path

from . import views

urlpatterns = [
    path("api/chat/conversations/", views.ConversationsView.as_view()),
    path("api/chat/conversations/<int:pk>/messages/", views.MessagesView.as_view()),
    path("api/chat/unread/", views.UnreadView.as_view()),
    path("api/admin/chat/support/", views.AdminSupportView.as_view()),
    path("api/admin/chat/support/<int:pk>/close/", views.AdminCloseView.as_view()),
]

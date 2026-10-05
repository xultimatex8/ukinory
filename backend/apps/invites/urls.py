from django.urls import path

from apps.invites.views import InviteAcceptView, InviteListCreateView

urlpatterns = [
    path("", InviteListCreateView.as_view(), name="invite-list-create"),
    path("<str:code>/accept/", InviteAcceptView.as_view(), name="invite-accept"),
]

from django.urls import path

from apps.invites.views import InviteAcceptView

urlpatterns = [
    path("<str:code>/accept/", InviteAcceptView.as_view(), name="invite-accept"),
]

from django.urls import path
from rest_framework_simplejwt import views as jwt_views

from .views import ChangePasswordView, ClaimGuestView, CurrentUserView, DeleteAccountView, GuestView, RegisterView

urlpatterns = [
    path("guest/", GuestView.as_view(), name="guest"),
    path("register/", RegisterView.as_view(), name="register"),
    path("guest/claim/", ClaimGuestView.as_view(), name="guest-claim"),
    path("token/", jwt_views.TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", jwt_views.TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", jwt_views.TokenBlacklistView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("me/delete/", DeleteAccountView.as_view(), name="delete-account"),
    path("me/password/", ChangePasswordView.as_view(), name="change-password"),
]
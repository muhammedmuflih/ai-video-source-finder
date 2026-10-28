
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("auth/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("auth/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("auth/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("auth/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    path("api/", include("finder.urls")),
]

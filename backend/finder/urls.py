
from django.urls import path

from . import views

app_name = "finder"

urlpatterns = [
    path("auth/csrf/", views.csrf_token, name="auth-csrf"),
    path("auth/signup/", views.sign_up, name="auth-signup"),
    path("auth/login/", views.sign_in, name="auth-login"),
    path("auth/google/start/", views.google_start, name="auth-google-start"),
    path("auth/logout/", views.sign_out, name="auth-logout"),
    path("auth/me/", views.current_user, name="auth-me"),
    path("health/", views.health_check, name="health-check"),
    path("search/", views.search_video, name="search-video"),
]

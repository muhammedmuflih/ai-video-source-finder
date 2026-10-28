from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.providers.base.constants import AuthError


class ProjectSocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(
        self, request, provider, error=None, exception=None, extra_context=None
    ):
        message = "google_cancelled" if error == AuthError.CANCELLED else "google_failed"
        query = urlencode({"auth_error": message})
        target = f"{settings.FRONTEND_BASE_URL}/login.html?{query}#signin"
        raise ImmediateHttpResponse(HttpResponseRedirect(target))

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


PASSWORD = "Correct-Horse-82!"


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        csrf = self.client.get(reverse("finder:auth-csrf"))
        self.csrf_token = csrf.json()["csrfToken"]

    def post_json(self, url, data, *, token=None):
        headers = {"content_type": "application/json"}
        if token is not None:
            headers["HTTP_X_CSRFTOKEN"] = token
        return self.client.post(url, data=data, **headers)

    def test_signup_login_session_and_logout(self):
        response = self.post_json(
            reverse("finder:auth-signup"),
            {"email": "  New.User@Example.com ", "password": PASSWORD},
            token=self.csrf_token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(User.objects.filter(username="new.user@example.com").exists())
        self.assertEqual(self.client.get(reverse("finder:auth-me")).json()["email"], "new.user@example.com")

        response = self.post_json(
            reverse("finder:auth-logout"), {}, token=self.client.cookies["csrftoken"].value
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("finder:auth-me")).status_code, 401)

        response = self.post_json(
            reverse("finder:auth-login"),
            {"email": "NEW.USER@example.com", "password": PASSWORD, "remember": False},
            token=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "new.user@example.com")
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_signup_validation_duplicate_and_csrf(self):
        url = reverse("finder:auth-signup")
        self.assertEqual(self.post_json(url, {"email": "bad", "password": PASSWORD}, token=self.csrf_token).status_code, 400)
        self.assertEqual(self.post_json(url, {"email": "user@example.com", "password": "short"}, token=self.csrf_token).status_code, 400)
        self.assertEqual(self.post_json(url, {"email": "user@example.com", "password": PASSWORD}, token=self.csrf_token).status_code, 201)
        self.assertEqual(self.post_json(url, {"email": "USER@example.com", "password": PASSWORD}, token=self.client.cookies["csrftoken"].value).status_code, 409)

        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            csrf_client.post(url, data={"email": "csrf@example.com", "password": PASSWORD}, content_type="application/json").status_code,
            403,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_sends_a_real_reset_link(self):
        User.objects.create_user(username="reset@example.com", email="reset@example.com", password=PASSWORD)
        response = self.client.post(
            "/auth/password_reset/",
            {"email": "reset@example.com"},
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/auth/reset/", mail.outbox[0].body)
        reset_link = next(line.strip() for line in mail.outbox[0].body.splitlines() if "/auth/reset/" in line)
        reset_path = urlsplit(reset_link).path
        response = self.client.get(reset_path, follow=True)
        self.assertEqual(response.status_code, 200)
        reset_confirm_path = response.request["PATH_INFO"]
        response = self.client.post(
            reset_confirm_path,
            {"new_password1": "Another-Secure-73!", "new_password2": "Another-Secure-73!"},
            HTTP_X_CSRFTOKEN=self.client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.get(username="reset@example.com").check_password("Another-Secure-73!"))

    @override_settings(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    def test_google_start_reports_missing_credentials(self):
        response = self.client.get(reverse("finder:auth-google-start"))
        self.assertEqual(response.status_code, 503)
        self.assertIn("GOOGLE_CLIENT_ID", response.json()["error"])

    @override_settings(GOOGLE_CLIENT_ID="test-client", GOOGLE_CLIENT_SECRET="test-secret")
    def test_google_start_uses_local_safe_next_url(self):
        response = self.client.get(reverse("finder:auth-google-start"), {"next": "https://attacker.invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("next=%2F", response.json()["url"])

    @override_settings(SOCIALACCOUNT_PROVIDERS={
        "google": {
            "APP": {"client_id": "test-client", "secret": "test-secret", "key": ""},
            "SCOPE": ["profile", "email"],
            "OAUTH_PKCE_ENABLED": True,
        }
    })
    def test_google_post_starts_stateful_oauth_redirect(self):
        response = self.client.post(
            "/accounts/google/login/?process=login&next=%2F",
            {
                "csrfmiddlewaretoken": self.client.cookies["csrftoken"].value,
                "process": "login",
                "next": "/",
            },
            HTTP_HOST="localhost:5173",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response["Location"])
        self.assertIn("state=", response["Location"])
        self.assertEqual(
            parse_qs(urlsplit(response["Location"]).query)["redirect_uri"][0],
            "http://localhost:5173/accounts/google/login/callback/",
        )

    def test_video_search_rejects_anonymous_user(self):
        response = self.client.post(reverse("finder:search-video"))
        self.assertEqual(response.status_code, 403)

    def test_health_check_remains_public(self):
        response = self.client.get(reverse("finder:health-check"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("finder.views.search_video_sources")
    @patch("finder.views.analyze_video")
    def test_authenticated_video_search_keeps_the_existing_api_response(self, analyze, search):
        user = User.objects.create_user(username="search@example.com", email="search@example.com", password=PASSWORD)
        self.client.force_login(user)
        csrf = self.client.get(reverse("finder:auth-csrf")).json()["csrfToken"]
        analyze.return_value = {"frames": [], "search_text": "test", "audio_transcript": ""}
        search.return_value = {"results": [], "services": ["mock"], "service_errors": []}

        response = self.client.post(
            reverse("finder:search-video"),
            {"video": SimpleUploadedFile("sample.mp4", b"video-bytes", content_type="video/mp4")},
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        analyze.assert_called_once()
        search.assert_called_once()

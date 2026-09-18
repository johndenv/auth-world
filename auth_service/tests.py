from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RegisterFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []

    def test_register_creates_inactive_user_and_stores_code(self):
        response = self.client.post(
            reverse("auth_service:register-user"),
            {
                "email": "user@test.com",
                "country_code": "55",
                "phone_with_ddd": "31997623668",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
            },
        )

        user = User.objects.get(email="user@test.com")
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("auth_service:verify-user"))
        self.assertTrue(user.check_password("SenhaForte123!"))
        self.assertEqual(user.phone, "5531997623668")
        self.assertFalse(user.is_active)

        code = cache.get(f"verify_{user.email}")
        self.assertIsNotNone(code)
        self.assertEqual(len(code), 6)
        self.assertEqual(self.client.session["pending_email"], user.email)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertIn(code, mail.outbox[0].body)

    def test_verify_with_correct_code_activates_user(self):
        user = User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            phone="5531997623668",
        )
        self.assertFalse(user.is_active)
        cache.set(f"verify_{user.email}", "123456", 600)

        session = self.client.session
        session["pending_email"] = user.email
        session.save()

        response = self.client.post(
            reverse("auth_service:verify-user"),
            {"cod": "123456"},
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("auth_service:login-user"))
        self.assertTrue(user.is_active)
        self.assertIsNone(cache.get(f"verify_{user.email}"))

    def test_verify_with_wrong_code_does_not_activate(self):
        user = User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            phone="5531997623668",
        )
        cache.set(f"verify_{user.email}", "123456", 600)

        session = self.client.session
        session["pending_email"] = user.email
        session.save()

        response = self.client.post(
            reverse("auth_service:verify-user"),
            {"cod": "999999"},
        )

        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(user.is_active)
        self.assertIsNotNone(cache.get(f"verify_{user.email}"))

    def test_inactive_user_cannot_login(self):
        User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            phone="5531997623668",
        )

        logged_in = self.client.login(
            username="user@test.com", password="SenhaForte123!"
        )
        self.assertFalse(logged_in)
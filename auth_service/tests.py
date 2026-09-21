import time

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from auth_service.views import LOGIN_BLOCK_KEY

from .forms import SubUserForm

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

    def test_register_creates_owner_with_admin_role(self):
        response = self.client.post(
            reverse("auth_service:register-user"),
            {
                "email": "boss@test.com",
                "country_code": "55",
                "phone_with_ddd": "31997623668",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="boss@test.com")
        self.assertTrue(user.is_owner)
        self.assertEqual(user.role, User.Roles.ADMIN)
        self.assertEqual(user.owner, user)

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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DashboardPermissionTests(TestCase):
    """Tela de cadastro de usuários: somente o administrador (dono) tem acesso."""

    def make_user(self, email, role, is_owner=False, owner=None):
        user = User.objects.create_user(
            email=email,
            password="SenhaForte123!",
            phone="5531997623668",
            role=role,
            is_owner=is_owner,
            is_active=True,
        )
        if owner is not None:
            user.owner = owner
            user.save(update_fields=["owner"])
        return user

    def setUp(self):
        self.owner = self.make_user(
            "owner@test.com", User.Roles.ADMIN, is_owner=True
        )
        self.owner.owner = self.owner
        self.owner.save(update_fields=["owner"])

    def test_sub_user_form_excludes_admin(self):
        form = SubUserForm()
        values = [value for value, _ in form.fields["role"].choices]
        self.assertNotIn(User.Roles.ADMIN, values)
        self.assertEqual(values, ["noob", "pro", "ultra"])

    def test_sub_user_cannot_receive_admin_role(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("auth_service:home"),
            {
                "email": "sub@test.com",
                "phone": "31997623668",
                "role": "admin",
                "password": "SenhaForte123!",
            },
        )
        # O formulário rejeita o cargo admin: re-renderiza com erro e não cria ninguém
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email="sub@test.com").exists())

    def test_owner_can_create_subusers(self):
        self.client.force_login(self.owner)
        for role in ("noob", "pro", "ultra"):
            email = f"sub-{role}@test.com"
            response = self.client.post(
                reverse("auth_service:home"),
                {
                    "email": email,
                    "phone": "31997623668",
                    "role": role,
                    "password": "SenhaForte123!",
                },
            )
            self.assertRedirects(response, reverse("core:work-area"))
            sub = User.objects.get(email=email)
            self.assertFalse(sub.is_owner)
            self.assertEqual(sub.role, role)
            self.assertTrue(sub.is_active)
            self.assertEqual(sub.owner, self.owner)
            self.assertEqual(sub.created_by, self.owner)

    def test_owner_sees_admin_on_dashboard(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("auth_service:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin")

    def test_non_owners_are_redirected_from_dashboard(self):
        noob = self.make_user("noob@test.com", User.Roles.NOOB, owner=self.owner)
        self.client.force_login(noob)
        response = self.client.get(reverse("auth_service:home"))
        self.assertRedirects(response, reverse("core:work-area"))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LoginRateLimitTests(TestCase):
    """Bloqueio progressivo do login por conta após tentativas inválidas."""

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.email = "user@test.com"
        self.user = User.objects.create_user(
            email=self.email,
            password="SenhaForte123!",
            phone="5531997623668",
            is_active=True,
        )

    def _login(self, client, password="errada"):
        return client.post(
            reverse("auth_service:login-user"),
            {"username": self.email, "password": password},
        )

    def _expire_block(self):
        """Simula o fim do bloqueio, fazendo o cache esquecer a punição atual."""
        cache.set(LOGIN_BLOCK_KEY.format(email=self.email), time.time() - 1, 60)

    def test_up_to_four_failures_are_normal(self):
        for _ in range(4):
            response = self._login(self.client)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Senha incorreta")
            self.assertNotContains(response, "bloqueada")

    def test_fifth_failure_blocks_for_one_minute(self):
        response = None
        for _ in range(5):
            response = self._login(self.client)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bloqueada")
        self.assertContains(response, "1 minuto")

        # Durante o bloqueio, até a senha correta é recusada
        response = self._login(self.client, "SenhaForte123!")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bloqueada")

    def test_sixth_failure_after_wait_blocks_for_five_minutes(self):
        for _ in range(5):
            self._login(self.client)
        self._expire_block()

        response = self._login(self.client)  # 6ª tentativa
        self.assertContains(response, "bloqueada")
        self.assertContains(response, "5 minutos")

    def test_eighth_failure_blocks_one_hour_and_alerts_owner(self):
        owner = User.objects.create_user(
            email="owner@test.com",
            password="SenhaForte123!",
            phone="5531997623668",
            role=User.Roles.ADMIN,
            is_owner=True,
            is_active=True,
        )
        self.user.owner = owner
        self.user.save(update_fields=["owner"])

        responselast = None
        for count in range(1, 9):
            responselast = self._login(self.client)
            # A cada bloqueio aplicado, simulamos o fim do prazo antes da
            # próxima tentativa (o contador de falhas permanece acumulado)
            if count in (5, 6, 7):
                self._expire_block()

        self.assertContains(responselast, "bloqueada")
        self.assertContains(responselast, "1 hora")

        # E-mail de alerta de segurança enviado ao dono real da conta
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [owner.email])
        self.assertIn(self.email, mail.outbox[0].body)

    def test_security_alert_goes_to_owner_itself_when_attacked(self):
        self.user.role = User.Roles.ADMIN
        self.user.is_owner = True
        self.user.owner = self.user
        self.user.save(update_fields=["role", "is_owner", "owner"])

        for _ in range(7):
            self._login(self.client)
            self._expire_block()

        response = self._login(self.client)  # 8ª tentativa
        self.assertContains(response, "1 hora")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.email])

    def test_successful_login_resets_counter(self):
        for _ in range(4):
            self._login(self.client)

        response = self._login(self.client, "SenhaForte123!")
        self.assertEqual(response.status_code, 302)  # login bem-sucedido

        # Nova "janela" de tentativas: 4 erros voltam a ser normais,
        # e o bloqueio só aparece na 5ª tentativa
        client2 = Client()
        for _ in range(4):
            response = self._login(client2)
            self.assertContains(response, "Senha incorreta")
        response = self._login(client2)  # 5ª tentativa após o reset
        self.assertContains(response, "bloqueada")
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import AuditLog
from .services import (
    accounts_under_attack,
    compromised_accounts,
    credential_stuffing_sources,
    failed_login_count,
    get_client_ip,
    record_audit,
    sanitize_actor,
)

User = get_user_model()


class SanitizeActorTests(TestCase):
    """Apenas identificadores que parecem e-mail são mantidos."""

    def test_email_is_normalized_and_kept(self):
        self.assertEqual(sanitize_actor(" User@Example.com "), "user@example.com")

    def test_password_typed_in_username_field_is_discarded(self):
        # Senha real digitada no campo de usuário por engano: NUNCA é gravada.
        for value in ("SenhaForte123!", "123456", "abc ", "not-an-email", "a@b"):
            self.assertEqual(sanitize_actor(value), "")

    def test_empty_values_are_safe(self):
        self.assertEqual(sanitize_actor(""), "")
        self.assertEqual(sanitize_actor(None), "")


class RecordAuditTests(TestCase):
    """A função record_audit grava todos os campos previstos no modelo."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_record_audit_stores_timestamp_action_actor_ip_device_reason(self):
        request = self.factory.post(
            "/login/",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/120.0",
        )
        record_audit(
            request,
            action=AuditLog.Action.LOGIN_FAILED,
            actor="alvo@example.com",
            reason="Senha incorreta ou conta inativa.",
        )

        log = AuditLog.objects.get()
        self.assertIsNotNone(log.timestamp)
        self.assertEqual(log.action, AuditLog.Action.LOGIN_FAILED)
        self.assertEqual(log.actor, "alvo@example.com")
        self.assertEqual(log.source_ip, "127.0.0.1")
        self.assertIn("Windows", log.device)
        self.assertIn("Chrome", log.device)
        self.assertEqual(log.reason, "Senha incorreta ou conta inativa.")
        self.assertEqual(log.status, AuditLog.Status.OPEN)

    def test_record_audit_never_stores_non_email_actor(self):
        request = self.factory.post("/login/")
        record_audit(
            request,
            action=AuditLog.Action.LOGIN_FAILED,
            actor="SenhaQueNuncaDeveSerLogada!",
            reason="Senha incorreta ou conta inativa.",
        )
        log = AuditLog.objects.get()
        self.assertEqual(log.actor, "")

    def test_get_client_ip_ignores_xff_unless_trusted(self):
        request = self.factory.post(
            "/login/", HTTP_X_FORWARDED_FOR="203.0.113.9"
        )
        self.assertEqual(get_client_ip(request), "127.0.0.1")

    @override_settings(TRUST_X_FORWARDED_FOR=True)
    def test_get_client_ip_uses_xff_when_trusted(self):
        request = self.factory.post(
            "/login/", HTTP_X_FORWARDED_FOR="203.0.113.9, 10.0.0.1"
        )
        self.assertEqual(get_client_ip(request), "203.0.113.9")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthAuditIntegrationTests(TestCase):
    """O fluxo de autenticação registra os eventos no AuditLog."""

    def setUp(self):
        cache.clear()
        mail.outbox = []

    def test_register_logs_audit(self):
        self.client.post(
            reverse("auth_service:register-user"),
            {
                "email": "user@test.com",
                "country_code": "55",
                "phone_with_ddd": "31997623668",
                "password": "SenhaForte123!",
                "password_confirm": "SenhaForte123!",
            },
        )

        log = AuditLog.objects.get(action=AuditLog.Action.REGISTER)
        self.assertEqual(log.actor, "user@test.com")
        self.assertEqual(log.user.email, "user@test.com")
        self.assertEqual(log.source_ip, "127.0.0.1")
        self.assertNotEqual(log.device, "")
        self.assertIn("criada", log.reason.lower())

    def test_verify_logs_account_activation(self):
        user = User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            is_active=False,
        )
        cache.set(f"verify_{user.email}", "123456", 600)
        session = self.client.session
        session["pending_email"] = user.email
        session.save()

        self.client.post(reverse("auth_service:verify-user"), {"cod": "123456"})

        log = AuditLog.objects.get(action=AuditLog.Action.ACCOUNT_ACTIVATED)
        self.assertEqual(log.actor, user.email)
        self.assertEqual(log.user, user)

    def test_login_success_logs_user(self):
        user = User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            is_active=True,
        )
        self.client.post(
            reverse("auth_service:login-user"),
            {"username": user.email, "password": "SenhaForte123!"},
        )

        log = AuditLog.objects.get(action=AuditLog.Action.LOGIN_SUCCESS)
        self.assertEqual(log.actor, "user@test.com")
        self.assertEqual(log.user, user)

    def test_failed_and_blocked_login_logged(self):
        User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            is_active=True,
        )
        for _ in range(5):
            self.client.post(
                reverse("auth_service:login-user"),
                {"username": "user@test.com", "password": "errada"},
            )

        self.assertEqual(
            AuditLog.objects.filter(action=AuditLog.Action.LOGIN_FAILED).count(),
            5,
        )
        # 6ª requisição (durante o bloqueio) registra LOGIN_BLOCKED
        self.client.post(
            reverse("auth_service:login-user"),
            {"username": "user@test.com", "password": "errada"},
        )
        blocked = AuditLog.objects.get(action=AuditLog.Action.LOGIN_BLOCKED)
        self.assertEqual(blocked.actor, "user@test.com")
        self.assertEqual(blocked.source_ip, "127.0.0.1")

    def test_password_in_username_field_never_reaches_the_log(self):
        """Se o usuário digitar a senha no campo errado, NADA é vazado."""
        User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            is_active=True,
        )
        self.client.post(
            reverse("auth_service:login-user"),
            {
                # Senha correta digitada por engano no campo de usuário
                "username": "SenhaForte123!",
                "password": "outraSenhaQualquer!",
            },
        )

        log = AuditLog.objects.get(action=AuditLog.Action.LOGIN_FAILED)
        self.assertEqual(log.actor, "")  # não parece e-mail -> descartado
        for field in (log.actor, log.reason, log.device, log.user_agent):
            self.assertNotIn("SenhaForte123", field)
        self.assertEqual(log.source_ip, "127.0.0.1")

    def test_logout_logs_audit(self):
        User.objects.create_user(
            email="user@test.com",
            password="SenhaForte123!",
            is_active=True,
        )
        self.client.login(username="user@test.com", password="SenhaForte123!")
        self.client.post(reverse("auth_service:logout"))

        log = AuditLog.objects.get(action=AuditLog.Action.LOGOUT)
        self.assertEqual(log.actor, "user@test.com")

    def test_subuser_creation_logs_audit(self):
        owner = User.objects.create_user(
            email="owner@test.com",
            password="SenhaForte123!",
            role=User.Roles.ADMIN,
            is_owner=True,
            is_active=True,
        )
        owner.owner = owner
        owner.save(update_fields=["owner"])

        self.client.force_login(owner)
        self.client.post(
            reverse("auth_service:home"),
            {
                "email": "sub@test.com",
                "phone": "31997623668",
                "role": "noob",
                "password": "SenhaForte123!",
            },
        )

        log = AuditLog.objects.get(action=AuditLog.Action.SUBUSER_CREATED)
        self.assertEqual(log.actor, "sub@test.com")
        self.assertEqual(log.user.email, "sub@test.com")
        self.assertIn("owner@test.com", log.reason)


class RecordActionAuditTests(TestCase):
    """Registro/estado/exclusão de dados também são auditados."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email="owner@test.com",
            password="SenhaForte123!",
            role=User.Roles.ADMIN,
            is_owner=True,
            is_active=True,
        )
        self.owner.owner = self.owner
        self.owner.save(update_fields=["owner"])
        self.client.force_login(self.owner)

    def test_create_record_logs_audit(self):
        self.client.post(
            reverse("core:record-create"), {"name": "Cliente Alfa"}
        )
        log = AuditLog.objects.get(action=AuditLog.Action.RECORD_CREATED)
        self.assertEqual(log.actor, "owner@test.com")
        self.assertIn("Cliente Alfa", log.reason)

    def test_status_change_and_delete_log_audit(self):
        record = self.owner.records.create(name="Cliente Beta")
        self.client.post(
            reverse("core:record-status", args=[record.id]),
            {"status": "ativo"},
        )
        changed = AuditLog.objects.get(
            action=AuditLog.Action.RECORD_STATUS_CHANGED
        )
        self.assertIn("Cliente Beta", changed.reason)

        self.client.post(reverse("core:record-delete", args=[record.id]))
        deleted = AuditLog.objects.get(action=AuditLog.Action.RECORD_DELETED)
        self.assertIn("Cliente Beta", deleted.reason)


class AttackDetectionTests(TestCase):
    """Heurísticas para DDoS / credential stuffing / contas comprometidas."""

    def test_failed_login_count_filters_by_actor_and_ip(self):
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_FAILED, actor="a@test.com", source_ip="1.1.1.1"
        )
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_FAILED, actor="a@test.com", source_ip="2.2.2.2"
        )
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_BLOCKED, actor="b@test.com", source_ip="1.1.1.1"
        )
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_FAILED, actor="a@test.com", source_ip="1.1.1.1"
        )

        self.assertEqual(failed_login_count(actor="a@test.com"), 3)
        self.assertEqual(failed_login_count(ip="1.1.1.1"), 3)
        self.assertEqual(failed_login_count(actor="c@test.com"), 0)

    def test_credential_stuffing_sources_found(self):
        for actor in ("a@test.com", "b@test.com", "c@test.com", "d@test.com"):
            for _ in range(3):
                AuditLog.objects.create(
                    action=AuditLog.Action.LOGIN_FAILED,
                    actor=actor,
                    source_ip="203.0.113.9",
                )
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_FAILED,
            actor="e@test.com",
            source_ip="198.51.100.7",
        )

        sources = credential_stuffing_sources(minutes=60, threshold=5)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["source_ip"], "203.0.113.9")
        self.assertEqual(sources[0]["attempts"], 12)
        self.assertEqual(sources[0]["actors"], 4)

    def test_accounts_under_attack_found(self):
        for _ in range(6):
            AuditLog.objects.create(
                action=AuditLog.Action.LOGIN_FAILED,
                actor="alvo@test.com",
                source_ip="198.51.100.7",
            )
        targets = accounts_under_attack(minutes=60, threshold=5)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["actor"], "alvo@test.com")
        self.assertEqual(targets[0]["attempts"], 6)

    def test_compromised_account_detected(self):
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_FAILED,
            actor="vitima@test.com",
            source_ip="198.51.100.7",
        )
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_SUCCESS,
            actor="vitima@test.com",
            source_ip="198.51.100.7",
        )
        # Conta sem falhas anteriores NÃO entra no relatório
        AuditLog.objects.create(
            action=AuditLog.Action.LOGIN_SUCCESS,
            actor="normal@test.com",
            source_ip="198.51.100.7",
        )

        compromised = compromised_accounts(days=7)
        self.assertEqual(compromised, ["vitima@test.com"])
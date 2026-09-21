from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    class Action(models.TextChoices):
        REGISTER = "REGISTER", _("Cadastro de conta")
        ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED", _("Conta ativada")
        SUBUSER_CREATED = "SUBUSER_CREATED", _("Criação de usuário")
        LOGIN_SUCCESS = "LOGIN_SUCCESS", _("Login bem-sucedido")
        LOGIN_FAILED = "LOGIN_FAILED", _("Login inválido")
        LOGIN_BLOCKED = "LOGIN_BLOCKED", _("Login bloqueado (rate limit)")
        LOGOUT = "LOGOUT", _("Logout")
        RECORD_CREATED = "RECORD_CREATED", _("Registro criado")
        RECORD_STATUS_CHANGED = "RECORD_STATUS_CHANGED", _("Status de registro alterado")
        RECORD_DELETED = "RECORD_DELETED", _("Registro excluído")

    class Status(models.TextChoices):
        OPEN = "open", _("Aberto")
        REVIEWED = "reviewed", _("Em análise")
        RESOLVED = "resolved", _("Resolvido")

    # --- Dados imutáveis (registrados automaticamente) ---
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(
        max_length=30,
        choices=Action.choices,
        db_index=True,
        verbose_name=_("ação"),
    )
    # Apenas valores que parecem e-mail são armazenados (nunca senhas)
    actor = models.CharField(
        max_length=254,
        blank=True,
        db_index=True,
        verbose_name=_("ator (e-mail)"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("usuário"),
    )
    source_ip = models.GenericIPAddressField(
        null=True, blank=True, db_index=True, verbose_name=_("IP de origem")
    )
    device = models.CharField(
        max_length=255, blank=True, verbose_name=_("dispositivo")
    )
    user_agent = models.CharField(
        max_length=500, blank=True, verbose_name=_("user agent")
    )
    reason = models.TextField(blank=True, verbose_name=_("motivo"))

    # --- Dados mutáveis (editáveis pelo superusuário no painel) ---
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
        verbose_name=_("situação"),
    )

    class Meta:
        ordering = ("-timestamp",)
        verbose_name = _("registro de auditoria")
        verbose_name_plural = _("registros de auditoria")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M:%S} {self.action} {self.actor or '—'}"
from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Painel de auditoria: consulta, investigação e acompanhamento.

    Metadados de autenticação são imutáveis (não editáveis). Apenas o
    status de tratamento (aberto/em análise/resolvido) pode ser alterado.
    """

    list_display = ("timestamp", "action", "actor", "source_ip", "device", "status")
    list_filter = ("action", "status", "timestamp")
    search_fields = ("actor", "source_ip", "device", "reason", "user__email")
    date_hierarchy = "timestamp"
    readonly_fields = (
        "timestamp",
        "action",
        "actor",
        "user",
        "source_ip",
        "device",
        "user_agent",
        "reason",
    )
    list_select_related = ("user",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "timestamp",
                    "action",
                    "status",
                )
            },
        ),
        (
            "Quem e de onde",
            {
                "fields": (
                    "actor",
                    "user",
                    "source_ip",
                    "device",
                    "user_agent",
                )
            },
        ),
        (
            "Motivo",
            {"fields": ("reason",)},
        ),
    )
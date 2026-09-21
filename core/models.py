from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Record(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', _('Pendente')
        BLOQUEADO = 'bloqueado', _('Bloqueado')
        ATIVO = 'ativo', _('Ativo')

    name = models.CharField(max_length=150, verbose_name=_('name'))
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDENTE,
        verbose_name=_('status'),
    )

    # Dono da organização a quem o registro pertence (escopo dos dados)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='records',
        verbose_name=_('owner'),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_records',
        verbose_name=_('created by'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('record')
        verbose_name_plural = _('records')
        ordering = ('-created_at',)

    def __str__(self):
        return self.name
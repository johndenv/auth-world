from django.db import models
import uuid
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _

# PermissionMixin para genrenciar permissões dos usuários
# Herdando a classe pronta de usuarios do django AbstractUser para criar os campos
# Herdando BaseUserManager para Gerenciar esses campos 


# Gerenciador do banco de usuários
class UserManager(BaseUserManager):
    # cria usuario comum
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The email is mandatory')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    # cria super usuario
    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_owner', True)
        extra_fields.setdefault('role', self.model.Roles.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        
        return self.create_user(email, password, **extra_fields)

# classe principal que gera o banco
class User(AbstractBaseUser, PermissionsMixin):
    class Roles(models.TextChoices):
        NOOB = 'noob', _('Noob')
        PRO = 'pro', _('Pro')
        ULTRA = 'ultra', _('Ultra')
        ADMIN = 'admin', _('Admin')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    # Cargo do usuário: noob, pro ou ultra
    role = models.CharField(
        max_length=10,
        choices=Roles.choices,
        default=Roles.NOOB,
        verbose_name=_('role'),
    )

    # Criador da conta: possui permissão máxima (administrador)
    is_owner = models.BooleanField(default=False, verbose_name=_('account owner'))

    # Usuário que criou esta conta (None para o criador da conta)
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        verbose_name=_('created by'),
    )

    # Dono da organização a que este usuário pertence
    owner = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='organization_members',
        verbose_name=_('owner'),
    )

    # Define o email como o campo de login único
    USERNAME_FIELD = 'email'

    # Campos obrigatórios ao criar via createsuperuser (além do USERNAME_FIELD e password)
    REQUIRED_FIELDS = []

    # Vincula o manager customizado à classe de Usuário
    objects = UserManager()

    def __str__(self):
        return self.email

    def can_manage_users(self):
        """Somente o criador da conta pode criar/gerenciar usuários."""
        return self.is_owner

    def can_change_state(self):
        return self.is_owner or self.role in (
            self.Roles.PRO,
            self.Roles.ULTRA,
        )

    def can_delete_records(self):
        return self.is_owner or self.role == self.Roles.ULTRA



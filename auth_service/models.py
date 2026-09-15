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

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        
        return self.create_user(email, password, **extra_fields)

# classe principal que gera o banco
class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Define o email como o campo de login único
    USERNAME_FIELD = 'email'

    # Campos obrigatórios ao criar via createsuperuser (além do USERNAME_FIELD e password)
    REQUIRED_FIELDS = []

    # Vincula o manager customizado à classe de Usuário
    objects = UserManager()

    def __str__(self):
        return self.email



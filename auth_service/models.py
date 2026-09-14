from django.db import models
import uuid
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin

# PermissionMixin para genrenciar permissões dos usuários
# Herdando a classe pronta de usuarios do django AbstractUser para criar os campos
# Herdando BaseUserManager para Gerenciar esses campos 


########################### CAMPOS DO BANCO ###########################
"""
UUID - chave primaria global.

password - Armazena o hash criptografado e seguro da senha do usuário (herdado de AbstractBaseUser).

last_login - Guarda a data e hora do último acesso do usuário ao sistema (herdado de AbstractBaseUser).

is_superuser - Define se o usuário tem todas as permissões do sistema de forma irrestrita (herdado de PermissionsMixin).

groups - Cria uma relação de muitos para muitos para agrupar usuários com cargos semelhantes (herdado de PermissionsMixin).

user_permissions - Permite atribuir permissões específicas diretamente a um usuário individual (herdado de PermissionsMixin).

identifier - Funciona como o login exclusivo do usuário, podendo ser um e-mail, CPF ou texto customizado.

name - Armazena o nome completo ou de exibição do usuário no sistema.

is_active - Controla se a conta está ativa ou bloqueada para realizar novos logins.

is_staff - Define se o usuário tem autorização para acessar o painel de administração do Django Admin.
"""
#######################################################################
# Gerenciador do banco de usuários
class UserManager(BaseUserManager):
    # cria usuario comum
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O email é obrigatório!')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

# classe principal que gera o banco
class User(AbstractBaseUser, PermissionsMixin):
    pass



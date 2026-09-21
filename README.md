# Auth Universal

Autenticação Django **pronta para usar em qualquer sistema**. Cadastro com e-mail, verificação por código, login, hierarquia de cargos e gestão de usuários. Feita para ser copiada e adaptada ao seu projeto.

---

## Funcionalidades

- **Cadastro** com e-mail, telefone (DDI + DDD) e senha.
- **Verificação de e-mail** por código de 6 dígitos (expira em 10 minutos).
- **Login e Logout** com e-mail + senha.
- **Rate limiting no login** com bloqueio progressivo (1 min → 5 min → 1 h + alerta por e-mail).
- **Usuário customizado** (`UUID` como PK, e-mail como campo de login).
- **Cargos hierárquicos**: `admin` (dono da conta), `ultra`, `pro`, `noob`.
- **Dashboard de gestão de usuários**: somente o ADMIN (criador da conta) cria e gerencia novos usuários e escolhe o cargo deles.
- **Área de trabalho de exemplo** com as ações *Registro*, *Estado* (pendente/bloqueado/ativo) e *Exclusão*.
- Banco de dados **PostgreSQL**.

## Stack

| Tecnologia | Versão |
|-----------|--------|
| Python | 3.14 |
| Django | 6.1.1 |
| psycopg | 3.3.6 (driver PostgreSQL) |
| django-anymail | 15.2 (envio de e-mail — Resend) |
| python-dotenv | 1.2.3 (configuração via `.env`) |

---

## Estrutura do projeto

```
auth world/
├── manage.py
├── .env                      # configurações sensíveis (não versionar)
├── authentication/           # pacote de configuração do Django
│   ├── settings.py
│   └── urls.py
├── auth_service/             # ⭐ APP DE AUTENTICAÇÃO (o que você quer reutilizar)
│   ├── models.py             # User + UserManager (cargos, dono da conta)
│   ├── forms.py              # UserForm, LoginForm, VerificationCode, SubUserForm
│   ├── views.py              # RegisterUser, VerifyCodeView, HomeView
│   ├── urls.py
│   ├── templates/auth_service/   # register.html, verify.html, login.html, home.html
│   └── static/auth_service/      # CSS e imagens
├── core/                     # app de EXEMPLO ("Área de trabalho" com registros)
│   ├── models.py             # Record (nome + status + dono)
│   ├── views.py              # WorkAreaView, CreateRecordView, ...
│   ├── templates/core/       # work_area.html
│   └── static/core/
└── venv/                     # ambiente virtual
```

> O app **`auth_service`** é a autenticação em si. O app **`core`** é uma demonstração de uma tela pós-login (para você substituir pela tela do *seu* sistema). Veja a seção [Adaptando para o seu projeto](#adaptando-para-o-seu-projeto).

---

## Fluxo de autenticação

```
/                 → Cadastro (quem se cadastra é o ADMIN / dono da conta)
/verify/          → Código de 6 dígitos enviado por e-mail (ativa a conta)
/login/           → Entrar com e-mail + senha
                  └─ ADMIN  → /home/ (dashboard de gestão de usuários)
                  └─ outros → redireciona para a Área de trabalho
```

### Cargos e permissões

| Cargo | Cria usuários | Cria registros | Muda estado | Exclui registros |
|-------|:---:|:---:|:---:|:---:|
| **admin** (dono) | ✅ | ✅ | ✅ | ✅ |
| **ultra** | ❌ | ✅ | ✅ | ✅ |
| **pro** | ❌ | ✅ | ✅ | ❌ |
| **noob** | ❌ | ✅ | ❌ | ❌ |

> O cargo `admin` é **exclusivo** de quem criou a conta (`is_owner=True`). Ele não pode ser atribuído a outro usuário.

---

## Como rodar localmente

### 1. Preparar o ambiente

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install Django==6.1.1 psycopg==3.3.6 django-anymail==15.2 python-dotenv==1.2.3
```

### 2. Criar o banco PostgreSQL

Conecte no seu PostgreSQL e crie (ou use) um banco. O projeto vem apontando para:

```
postgresql://USER:PASSWORD@localhost:5432/postgres
```

### 3. Configurar o `.env*`

Copie/ajuste estas variáveis (existe um `.env` no projeto):

```env
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=coloque-uma-chave-secreta-segura

DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=sua-senha
DB_HOST=localhost
DB_PORT=5432

# E-mail
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
RESEND_API_KEY=
DEFAULT_FROM_EMAIL=nao-responder@seudominio.com
```

> **Para testar em dev** deixe `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` e o código de verificação aparecerá no terminal.
> **Para produção** use `EMAIL_BACKEND=anymail.backends.resend.EmailBackend` e preencha `RESEND_API_KEY` (a chave do [Resend](https://resend.com)).

### 4. Migrar e subir

```bash
python manage.py migrate
python manage.py runserver
```

Acesse `http://localhost:8000/` e crie sua conta.

---

## Rate limiting do login

Proteção progressiva contra tentativas de senha erradas **por conta** (por e-mail). O contador é guardado no cache do Django e zera após um login bem-sucedido.

| Tentativa inválida | Comportamento |
|-------------------|---------------|
| 1ª–4ª | Apenas **"Senha incorreta"** (comportamento normal) |
| 5ª | **Bloqueio de 1 minuto** |
| 6ª (após esperar o prazo passar) | **Bloqueio de 5 minutos** |
| 7ª | Permanece **5 minutos** |
| 8ª | **Bloqueio de 1 hora** + **e-mail de alerta** enviado ao dono real da conta |

> - Durante o bloqueio, até a senha correta é recusada e a mensagem mostra o tempo restante em segundos.
> - O e-mail de alerta sai **apenas uma vez** (na 8ª) e vai para o administrador da organização (se a conta atacada for um sub-usuário) ou para o próprio e-mail (se a conta atacada for o admin/dono).
> - Config viável em `auth_service/views.py` (`RateLimitedLoginView`): `MAX_FREE_ATTEMPTS`, `BLOCK_1_MINUTE`, `BLOCK_5_MINUTES`, `BLOCK_1_HOUR`.

---

## Adaptando para o seu projeto

Este é o foco do projeto: **reutilizar a autenticação em outro sistema Django**.

### Caso A — Projeto novo (recomendado)

1. Copie as pastas `auth_service/` e `authentication/` para dentro do seu projeto (ou clone este repositório e crie sua lógica nos apps `core`/novos).
2. No `settings.py` do seu projeto:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "anymail",
    "auth_service",          # ← autenticação
    "core",                  # ← app de exemplo (pode remover se não quiser)
]

AUTH_USER_MODEL = "auth_service.User"   # ← OBRIGATÓRIO antes da primeira migrate
```

3. Inclua as URLs no `urls.py` do projeto:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("auth_service.urls")),   # autenticação (/, /verify/, /login/, /home/)
    path("", include("core.urls")),           # exemplo (pode remover)
]
```

4. Configure os redirecionamentos:

```python
LOGIN_URL = "auth_service:login-user"
LOGIN_REDIRECT_URL = "auth_service:home"
LOGOUT_REDIRECT_URL = "auth_service:login-user"
```

5. Rode `python manage.py migrate` e pronto.

> **Atenção:** configure `AUTH_USER_MODEL` **antes** da primeira `migrate`. Depois da base criada, não dá para simplesmente trocar o modelo de usuário.

### Caso B — Projeto existente com usuário próprio

Se o seu sistema já tem um modelo de usuário, você tem duas opções:

**Opção 1 — Adotar o modelo desta autenticação (mais simples):**
Apague o seu app de usuário (ou não o registre) e use `auth_service.User` como o modelo oficial, configurando `AUTH_USER_MODEL` em uma base nova.

**Opção 2 — Migrar sua base atual:**
1. Copie os campos do `User` (`role`, `is_owner`, `owner`, `created_by`, `phone`).
2. Adapte seu `manager` para incluir `create_user`/`create_superuser` deste projeto.
3. Copie os métodos de permissão (`can_manage_users`, `can_change_state`, `can_delete_records`).
4. Copie `forms.py`, `views.py` e `templates/` trocando as referências de URL para o seu app.

### Pontos de adaptação importantes

| O que | Onde | Como adaptar |
|-------|------|--------------|
| Tela pós-login | `LOGIN_REDIRECT_URL` no `settings.py` | Aponte para a URL raiz do **seu** sistema |
| Tela pós-criação de usuário | `success_url` em `HomeView` (`auth_service/views.py`) | Troque `core:work-area` pela URL do seu sistema |
| Redirecionamento de usuário comum | `handle_no_permission` em `HomeView` | Troque `core:work-area` pela URL padrão |
| App de exemplo | app `core` | Remova `core` de `INSTALLED_APPS` + URLs e ajuste os pontos acima |
| Campos do usuário | `auth_service/models.py` | Adicione campos novos (ex.: `nome`) e gere migrações |
| E-mail | `.env` (`EMAIL_BACKEND`, `RESEND_API_KEY`) | Troque o provedor (o projeto usa Anymail, que suporta vários) |

### Usando as permissões no SEU código

No seu sistema você pode controlar acesso direto nos modelos:

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

User = get_user_model()
OwnerOnly = type("OwnerOnly", (LoginRequiredMixin, UserPassesTestMixin), {
    "test_func": lambda self: self.request.user.can_manage_users(),
})
```

Ou, de forma mais direta, dentro de qualquer view:

```python
def minha_view(request):
    user = request.user
    if user.can_manage_users():      # admin/dono
        ...
    if user.can_change_state():      # admin, ultra, pro
        ...
    if user.can_delete_records():    # admin, ultra
        ...
    if user.role == User.Roles.NOOB: # cargo específico
        ...
```

### Exemplo de uso do usuário em templates

```django
{% if user.can_manage_users %}
    <a href="{% url 'auth_service:home' %}">Gerenciar usuários</a>  {# só para o admin #}
{% endif %}

Cargo: {{ user.get_role_display }}
```

---

## URLs da autenticação

| URL | Nome | Descrição |
|-----|------|-----------|
| `/` | `auth_service:register-user` | Criar conta (vira admin/dono) |
| `/verify/` | `auth_service:verify-user` | Digitar o código de e-mail |
| `/login/` | `auth_service:login-user` | Entrar |
| `/home/` | `auth_service:home` | Dashboard de gestão de usuários (só admin) |
| `/logout/` | `auth_service:logout` | Sair |

> A área de trabalho (`core`) usa `/work-area/`, `/records/create/`, `/records/<id>/status/` e `/records/<id>/delete/`.

---

## Como o código de verificação funciona

1. O cadastro gera um código de 6 dígitos.
2. O código fica no **cache** do Django por 10 minutos (chave `verify_<email>`).
3. É enviado por e-mail (`core/email.py` → `send_verification_email`).
4. Ao acertar o código, a conta é ativada (`is_active = True`).

Extras: o usuário nasce inativo no cadastro, a sessão guarda o e-mail pendente, e o cache é limpo após a verificação.

---

## Personalização visual

Os templates e CSS ficam em:

```
auth_service/templates/auth_service/    # register, verify, login, home
auth_service/static/auth_service/css/   # register.css, login.css, dashboard.css
core/templates/core/                    # work_area.html
core/static/core/css/                   # work_area.css
```

A imagem de fundo das telas (`espada.jpg`) é só um placeholder — troque ou remove no template.

---

## Testes

```bash
python manage.py test
```

São **21 testes** cobrindo: cadastro, ativação por código, papel de admin no cadastro, restrição da dashboard ao admin, criação de sub-usuários (com bloqueio do cargo `admin`), a matriz de permissões da área de trabalho (registro/estado/exclusão por cargo e isolamento por organização) e o **rate limiting** do login (bloqueios progressivos de 1 min / 5 min / 1 h + e-mail de alerta e reset do contador).

---

## Dúvidas comuns

- **Preciso criar um banco diferente do `postgres`?** Não. A string `postgresql://postgres:John19$$@localhost:5432/postgres` usa o banco padrão. Em produção crie um banco dedicado e ajuste o `.env`.
- **O e-mail não chega em desenvolvimento?** Troque para `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` e veja o código no terminal.
- **Posso mudar os cargos?** Sim — edite `User.Roles` em `auth_service/models.py` e ajuste os métodos `can_*` (e o `SubUserForm` se quiser liberar/bloquear cargos na criação).
- **Como faço o usuário logar direto na minha tela?** Mude `LOGIN_REDIRECT_URL` para a URL do seu sistema (ex.: `"meuapp:home"`).
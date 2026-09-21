import random
import time

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, FormView

from audit_logs.models import AuditLog
from audit_logs.services import record_audit
from core.email import send_security_alert_email, send_verification_email
from .forms import LoginForm, SubUserForm, UserForm, VerificationCode

User = get_user_model()

CACHE_PREFIX = 'verify_'
CODE_TIMEOUT = 600  # 10 minutos

# Rate limit de login (por conta)
MAX_FREE_ATTEMPTS = 4          # tentativas 1–4: apenas "Senha incorreta"
BLOCK_STEP_1 = 5               # 5ª tentativa inválida → bloqueio de 1 minuto
BLOCK_STEP_2 = 6               # 6ª tentativa  → bloqueio de 5 minutos
BLOCK_STEP_3 = 8               # 8ª tentativa  → bloqueio de 1 hora e e-mail de alerta
BLOCK_1_MINUTE = 60
BLOCK_5_MINUTES = 300
BLOCK_1_HOUR = 3600
LOCK_TTL = BLOCK_1_HOUR * 2    # tempo de vida do contador no cache
FAILED_ATTEMPTS_KEY = 'login_fail_{email}'
LOGIN_BLOCK_KEY = 'login_block_{email}'
ALERT_SENT_KEY = 'login_alert_sent_{email}'


def _login_email(request):
    """Email informado no formulário de login (em minúsculas)."""
    return (request.POST.get("username") or "").strip().lower()


def _block_duration_for(fail_count):
    """Punição de acordo com o número de tentativas inválidas."""
    if fail_count >= BLOCK_STEP_3:
        return BLOCK_1_HOUR
    if fail_count >= BLOCK_STEP_2:
        return BLOCK_5_MINUTES
    if fail_count >= BLOCK_STEP_1:
        return BLOCK_1_MINUTE
    return 0


def _format_duration(seconds):
    if seconds >= BLOCK_1_HOUR:
        return "1 hora"
    if seconds >= BLOCK_5_MINUTES:
        return "5 minutos"
    return "1 minuto"


class AuditLogoutView(LogoutView):
    """Logout que registra a saída no log de auditoria antes de encerrar a sessão."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            record_audit(
                request,
                action=AuditLog.Action.LOGOUT,
                actor=request.user.email,
                user=request.user,
                reason="Logout concluído.",
            )
        return super().dispatch(request, *args, **kwargs)


class RateLimitedLoginView(LoginView):
    """Login com bloqueio progressivo por conta após várias tentativas inválidas.

    1ª–4ª tentativa: comportamento normal ("Senha incorreta").
    5ª tentativa: bloqueio de 1 minuto.
    6ª tentativa (após esperar): bloqueio de 5 minutos.
    8ª tentativa: bloqueio de 1 hora + e-mail de alerta ao dono real da conta.
    """

    template_name = "auth_service/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def _block_key(self, email):
        return LOGIN_BLOCK_KEY.format(email=email)

    def _fail_key(self, email):
        return FAILED_ATTEMPTS_KEY.format(email=email)

    def _alert_key(self, email):
        return ALERT_SENT_KEY.format(email=email)

    def get_block_until(self, email):
        return cache.get(self._block_key(email))

    def is_blocked(self, email):
        """True enquanto a punição estiver vigente."""
        if not email:
            return False
        blocked_until = self.get_block_until(email)
        if not blocked_until:
            return False
        if blocked_until <= time.time():
            # Prazo expirado: libera o acesso, mas mantém o contador acumulado
            cache.delete(self._block_key(email))
            return False
        return True

    def reset(self, email):
        """Zera contador/bloqueio após um login bem-sucedido."""
        cache.delete(self._fail_key(email))
        cache.delete(self._block_key(email))
        cache.delete(self._alert_key(email))

    def register_failed_attempt(self, email):
        """Registra mais uma tentativa inválida e aplica a punição. Retorna a
        duração do bloqueio (0 = sem bloqueio)."""
        key = self._fail_key(email)
        fail_count = cache.get(key, 0) + 1
        cache.set(key, fail_count, LOCK_TTL)

        duration = _block_duration_for(fail_count)
        if not duration:
            return 0

        cache.set(self._block_key(email), time.time() + duration, duration + 5)

        # A partir da 8ª tentativa, envia e-mail de alerta ao dono real da conta
        if (
            fail_count >= BLOCK_STEP_3
            and not cache.get(self._alert_key(email))
        ):
            cache.set(self._alert_key(email), True, LOCK_TTL)
            send_security_alert_email(email)

        return duration

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        email = _login_email(request)

        if email and self.is_blocked(email):
            remaining = max(int(self.get_block_until(email) - time.time()), 0)
            record_audit(
                request,
                action=AuditLog.Action.LOGIN_BLOCKED,
                actor=email,
                reason="Tentativa bloqueada por limite de tentativas (rate limit).",
            )
            form.add_error(
                None,
                f"Conta bloqueada temporariamente. Tente novamente em "
                f"{remaining} segundo(s).",
            )
            return self.render_to_response(self.get_context_data(form=form))

        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        email = _login_email(self.request)
        # AÇÃO/ATOR: apenas o e-mail informado é sanitizado e gravado.
        # REGRA DE SEGURANÇA: a senha (mesmo que digitada por engano no
        # campo de usuário) nunca chega ao log — o valor que não parece
        # e-mail é descartado por record_audit.
        if email:
            record_audit(
                self.request,
                action=AuditLog.Action.LOGIN_FAILED,
                actor=email,
                reason="Senha incorreta ou conta inativa.",
            )
            duration = self.register_failed_attempt(email)
            if duration:
                form.add_error(
                    None,
                    f"Muitas tentativas inválidas. Conta bloqueada por "
                    f"{_format_duration(duration)}.",
                )
        return super().form_invalid(form)

    def form_valid(self, form):
        email = _login_email(self.request)
        self.reset(email)
        record_audit(
            self.request,
            action=AuditLog.Action.LOGIN_SUCCESS,
            actor=email,
            user=form.get_user(),
            reason="Login bem-sucedido.",
        )
        return super().form_valid(form)


class RegisterUser(CreateView):
    template_name = "auth_service/register.html"
    form_class = UserForm
    model = User

    def form_valid(self, form):
        # O usuário registrado é o criador da conta (administrador)
        user = form.save(commit=False)
        user.is_active = False
        user.is_owner = True
        user.role = User.Roles.ADMIN
        user.save()
        # O dono da organização é ele mesmo
        user.owner = user
        user.save(update_fields=['owner'])

        # Gera o código de verificação
        cod_verification = str(random.randint(100000, 999999))

        # Guarda o código no cache, vinculado ao email do usuário
        cache.set(f"{CACHE_PREFIX}{user.email}", cod_verification, CODE_TIMEOUT)

        # Envia o código por email
        send_verification_email(user.email, cod_verification)

        # Guarda o email na sessão para a tela de verificação
        self.request.session['pending_email'] = user.email

        record_audit(
            self.request,
            action=AuditLog.Action.REGISTER,
            actor=user.email,
            user=user,
            reason="Nova conta criada (aguardando verificação de e-mail).",
        )

        return redirect(reverse_lazy('auth_service:verify-user'))


class VerifyCodeView(FormView):
    template_name = 'auth_service/verify.html'
    form_class = VerificationCode
    success_url = reverse_lazy('auth_service:login-user')

    def form_valid(self, form):
        email = self.request.session.get('pending_email')
        if not email:
            form.add_error('cod', 'Nenhuma conta pendente de verificação.')
            return self.form_invalid(form)

        cod_verification = str(form.cleaned_data['cod'])
        cod_cached = cache.get(f"{CACHE_PREFIX}{email}")

        if cod_cached != cod_verification:
            form.add_error('cod', 'Código inválido ou expirado.')
            return self.form_invalid(form)

        # Código correto: ativa a conta
        user = get_object_or_404(User, email=email, is_active=False)
        user.is_active = True
        user.save(update_fields=['is_active'])

        # Limpa o código do cache e a sessão
        cache.delete(f"{CACHE_PREFIX}{email}")
        self.request.session.pop('pending_email', None)

        record_audit(
            self.request,
            action=AuditLog.Action.ACCOUNT_ACTIVATED,
            actor=email,
            user=user,
            reason="E-mail verificado com o código de 6 dígitos.",
        )

        return super().form_valid(form)


class HomeView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Dashboard: cadastro de usuários. Somente o criador da conta."""

    template_name = 'auth_service/home.html'
    form_class = SubUserForm
    success_url = reverse_lazy('core:work-area')

    def test_func(self):
        return self.request.user.can_manage_users()

    def handle_no_permission(self):
        # Usuários comuns (noob/pro/ultra) vão direto para a área de trabalho
        return redirect(reverse_lazy('core:work-area'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['members'] = User.objects.filter(owner=self.request.user)
        return context

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_owner = False
        user.owner = self.request.user
        user.created_by = self.request.user
        # O cargo admin é exclusivo do criador da conta
        if user.role == User.Roles.ADMIN:
            user.role = User.Roles.NOOB
        user.save()

        record_audit(
            self.request,
            action=AuditLog.Action.SUBUSER_CREATED,
            actor=user.email,
            user=user,
            reason=f"Usuário criado na dashboard por {self.request.user.email}.",
        )
        return super().form_valid(form)
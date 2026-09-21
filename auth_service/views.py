import random

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, FormView

from core.email import send_verification_email
from .forms import UserForm, VerificationCode

User = get_user_model()

CACHE_PREFIX = 'verify_'
CODE_TIMEOUT = 600  # 10 minutos


class RegisterUser(CreateView):
    template_name = "auth_service/register.html"
    form_class = UserForm
    model = User

    def form_valid(self, form):
        # Cria o usuário ainda inativo
        user = form.save(commit=False)
        user.is_active = False
        user.save()

        # Gera o código de verificação
        cod_verification = str(random.randint(100000, 999999))

        # Guarda o código no cache, vinculado ao email do usuário
        cache.set(f"{CACHE_PREFIX}{user.email}", cod_verification, CODE_TIMEOUT)

        # Envia o código por email
        send_verification_email(user.email, cod_verification)

        # Guarda o email na sessão para a tela de verificação
        self.request.session['pending_email'] = user.email

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

        return super().form_valid(form)


class HomeView(LoginRequiredMixin, TemplateView):
    """Tela de sucesso após o login."""

    template_name = 'auth_service/home.html'
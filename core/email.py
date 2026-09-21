from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model


def send_verification_email(recipient_email, code, timeout_minutes=10):
    """Envia o código de verificação por email."""
    send_mail(
        subject="Código de verificação",
        message=(
            "Bem-vindo(a)!\n\n"
            f"Seu código de verificação é: {code}\n"
            f"O código expira em {timeout_minutes} minutos."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient_email],
        fail_silently=False,
    )


def send_security_alert_email(account_email):
    """Envia alerta de segurança ao dono real da conta após muitas tentativas
    de login inválidas na conta informada."""
    User = get_user_model()
    user = User.objects.filter(email__iexact=account_email).first()
    if not user:
        return

    # O "dono real" é o administrador da organização (ou a própria conta)
    recipient = user.owner if user.owner_id else user

    send_mail(
        subject="Alerta de segurança: muitas tentativas de login",
        message=(
            "Detectamos muitas tentativas de login inválidas na conta "
            f"{user.email}.\n\n"
            "Se foi você, ignore este aviso.\n"
            "Se NÃO foi você, sua conta pode estar sob ataque — "
            "troque a senha imediatamente.\n\n"
            "Equipe de segurança"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient.email],
        fail_silently=False,
    )
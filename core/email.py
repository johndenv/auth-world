from django.conf import settings
from django.core.mail import send_mail


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
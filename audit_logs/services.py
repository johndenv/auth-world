import logging
import re
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import AuditLog

logger = logging.getLogger(__name__)

# Um "ator" só é aceito se parecer um e-mail real. Qualquer outro valor
# (ex.: senha digitada por engano no campo de usuário) é DESCARTADO.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _trust_xff():
    from django.conf import settings

    return getattr(settings, "TRUST_X_FORWARDED_FOR", False)


def get_client_ip(request):
    """IP de origem da requisição (REMOTE_ADDR, ou X-Forwarded-For se o
    projeto explicitamente confiar em proxy via TRUST_X_FORWARDED_FOR)."""
    meta = getattr(request, "META", None)
    if not meta:
        return None
    if _trust_xff() and meta.get("HTTP_X_FORWARDED_FOR"):
        return meta["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
    return meta.get("REMOTE_ADDR")


def parse_device(user_agent):
    """Resumo simples de sistema operacional + navegador a partir do User-Agent."""
    ua = (user_agent or "").lower()
    if not ua:
        return "Desconhecido"

    os_info = "SO desconhecido"
    if "windows" in ua:
        os_info = "Windows"
    elif "android" in ua:
        os_info = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_info = "iOS"
    elif "mac os" in ua or "macintosh" in ua:
        os_info = "macOS"
    elif "linux" in ua:
        os_info = "Linux"

    browser = "Navegador desconhecido"
    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "chrome" in ua:
        browser = "Chrome"
    elif "safari" in ua:
        browser = "Safari"

    return f"{os_info} | {browser}"


def sanitize_actor(value):
    """Mantém apenas identificadores que pareçam e-mail.

    Nunca armazenar senha: se o usuário digitar a senha (ou qualquer valor
    não-e-mail) no campo de usuário por engano, o valor é descartado.
    """
    value = (value or "").strip().lower()[:254]
    if not value or not _EMAIL_RE.match(value):
        return ""
    return value


def record_audit(request, *, action, actor="", user=None, reason=""):
    """Grava um registro de auditoria.

    REGRA DE SEGURANÇA: este método NUNCA recebe a senha. O `actor` é
    sanitizado (só e-mails) e o `reason` deve conter apenas texto fixo.
    Falha na gravação nunca interrompe o fluxo de autenticação.
    """
    actor = sanitize_actor(actor)
    reason = (reason or "").strip()[:5000]
    meta = getattr(request, "META", None) or {}
    user_agent = (meta.get("HTTP_USER_AGENT") or "")[:500]

    try:
        AuditLog.objects.create(
            action=action,
            actor=actor,
            user=user if (user is not None and user.pk) else None,
            source_ip=get_client_ip(request),
            device=parse_device(user_agent),
            user_agent=user_agent,
            reason=reason,
        )
    except Exception:
        logger.exception("Falha ao registrar auditoria")


# ---------------------------------------------------------------------------
# Análise de segurança: DDoS / Credential Stuffing / contas comprometidas
# ---------------------------------------------------------------------------

_FAILED_ACTIONS = (AuditLog.Action.LOGIN_FAILED, AuditLog.Action.LOGIN_BLOCKED)


def _since(minutes):
    return timezone.now() - timedelta(minutes=minutes)


def failed_login_count(*, actor=None, ip=None, minutes=60):
    """Quantidade de tentativas de login inválidas/bloqueadas em um intervalo.

    Filtra por conta (`actor`) e/ou origem (`ip`). Usado para detectar
    credential stuffing (muitas falhas na mesma conta) e força bruta.
    """
    qs = AuditLog.objects.filter(action__in=_FAILED_ACTIONS)
    if minutes is not None:
        qs = qs.filter(timestamp__gte=_since(minutes))
    if actor:
        qs = qs.filter(actor=actor)
    if ip:
        qs = qs.filter(source_ip=ip)
    return qs.count()


def credential_stuffing_sources(minutes=60, threshold=10):
    """Origens (IPs) com muitas falhas distribuídas entre várias contas.

    Padrão típico de credential stuffing / força bruta distribuída: um IP
    (bot/farm) tenta senhas em muitas contas. Retorna dicts para análise.
    """
    qs = AuditLog.objects.filter(
        action__in=_FAILED_ACTIONS,
    ).exclude(source_ip__isnull=True)
    if minutes is not None:
        qs = qs.filter(timestamp__gte=_since(minutes))
    qs = (
        qs.values("source_ip")
        .annotate(attempts=Count("id"), actors=Count("actor", distinct=True))
        .filter(attempts__gte=threshold)
        .order_by("-attempts")
    )
    return list(qs)


def accounts_under_attack(minutes=60, threshold=5):
    """Contas com muitas falhas recentes (possível alvo de brute force)."""
    qs = AuditLog.objects.filter(
        action__in=_FAILED_ACTIONS,
    ).exclude(actor="")
    if minutes is not None:
        qs = qs.filter(timestamp__gte=_since(minutes))
    qs = (
        qs.values("actor")
        .annotate(attempts=Count("id"), ips=Count("source_ip", distinct=True))
        .filter(attempts__gte=threshold)
        .order_by("-attempts")
    )
    return list(qs)


def compromised_accounts(days=7):
    """Contas provavelmente comprometidas.

    Critério: a conta sofreu falhas/bloqueios e depois teve um login
    bem-sucedido dentro da janela (padrão de senha roubada + entrada do
    atacante, ou do dono após clicar no e-mail de alerta).
    """
    since = _since(days * 24 * 60)
    failed_qs = AuditLog.objects.filter(
        action__in=_FAILED_ACTIONS, timestamp__gte=since
    ).exclude(actor="")
    actors = set(failed_qs.values_list("actor", flat=True))

    success_qs = (
        AuditLog.objects.filter(
            action=AuditLog.Action.LOGIN_SUCCESS,
            timestamp__gte=since,
        )
        .exclude(actor="")
        .values("actor")
        .distinct()
    )
    return [
        row["actor"] for row in success_qs if row["actor"] in actors
    ]
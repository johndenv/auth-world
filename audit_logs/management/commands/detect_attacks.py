from django.core.management.base import BaseCommand

from audit_logs.services import (
    accounts_under_attack,
    compromised_accounts,
    credential_stuffing_sources,
)


class Command(BaseCommand):
    help = (
        "Analisa o log de auditoria e reporta indícios de DDoS, "
        "credential stuffing e contas comprometidas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=60,
            help="Janela (minutos) para falhas recentes (padrão: 60).",
        )
        parser.add_argument(
            "--ip-threshold",
            type=int,
            default=10,
            help="Falhas mínimas por IP para ser listado (padrão: 10).",
        )
        parser.add_argument(
            "--account-threshold",
            type=int,
            default=5,
            help="Falhas mínimas por conta para ser listada (padrão: 5).",
        )
        parser.add_argument(
            "--compromised-days",
            type=int,
            default=7,
            help="Janela (dias) para detectar contas comprometidas (padrão: 7).",
        )

    def handle(self, *args, **options):
        minutes = options["minutes"]
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"== Indícios nos últimos {minutes} min =="
            )
        )

        sources = credential_stuffing_sources(
            minutes=minutes, threshold=options["ip_threshold"]
        )
        if sources:
            for row in sources:
                self.stdout.write(
                    f"[IP] {row['source_ip']} -> {row['attempts']} falhas "
                    f"em {row['actors']} contas"
                )
        else:
            self.stdout.write("Nenhuma origem com muitas falhas.")

        targets = accounts_under_attack(
            minutes=minutes, threshold=options["account_threshold"]
        )
        if targets:
            for row in targets:
                self.stdout.write(
                    f"[CONTA] {row['actor']} -> {row['attempts']} falhas "
                    f"de {row['ips']} IP(s) distintos"
                )
        else:
            self.stdout.write("Nenhuma conta sob ataque.")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"== Contas provavelmente comprometidas "
                f"({options['compromised_days']} dias) =="
            )
        )
        compromised = compromised_accounts(days=options["compromised_days"])
        if compromised:
            for actor in compromised:
                self.stdout.write(f"[COMPROMETIDA] {actor}")
        else:
            self.stdout.write("Nenhuma conta comprometida detectada.")
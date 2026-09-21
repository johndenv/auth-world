from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Record

User = get_user_model()


def make_user(email, role, is_owner=False, owner=None):
    user = User.objects.create_user(
        email=email,
        password="SenhaForte123!",
        phone="5531997623668",
        role=role,
        is_owner=is_owner,
        is_active=True,
    )
    if owner is not None:
        user.owner = owner
        user.save(update_fields=["owner"])
    return user


def create_record(client, owner):
    client.post(reverse("core:record-create"), {"name": "Registro teste"})
    return Record.objects.get(owner=owner)


class WorkAreaPermissionTests(TestCase):
    """Ações registro/estado/exclusão conforme o cargo."""

    def setUp(self):
        self.owner = make_user("owner@test.com", User.Roles.ADMIN, is_owner=True)
        self.owner.owner = self.owner
        self.owner.save(update_fields=["owner"])

    def test_owner_can_register_change_state_and_delete(self):
        self.client.force_login(self.owner)
        record = create_record(self.client, self.owner)

        response = self.client.post(
            reverse("core:record-status", args=[record.pk]), {"status": "ativo"}
        )
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, "ativo")

        response = self.client.post(
            reverse("core:record-delete", args=[record.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Record.objects.filter(pk=record.pk).exists())

    def test_noob_can_only_create_records(self):
        noob = make_user("noob@test.com", User.Roles.NOOB, owner=self.owner)
        self.client.force_login(noob)

        response = self.client.post(
            reverse("core:record-create"), {"name": "Registro noob"}
        )
        self.assertEqual(response.status_code, 302)
        record = Record.objects.get(owner=self.owner)
        self.assertEqual(record.created_by, noob)

        response = self.client.post(
            reverse("core:record-status", args=[record.pk]), {"status": "ativo"}
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse("core:record-delete", args=[record.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Record.objects.filter(pk=record.pk).exists())

    def test_pro_can_change_state_but_not_delete(self):
        pro = make_user("pro@test.com", User.Roles.PRO, owner=self.owner)
        self.client.force_login(pro)

        create_record(self.client, self.owner)
        record = Record.objects.get(owner=self.owner)

        response = self.client.post(
            reverse("core:record-status", args=[record.pk]),
            {"status": "bloqueado"},
        )
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, "bloqueado")

        response = self.client.post(
            reverse("core:record-delete", args=[record.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Record.objects.filter(pk=record.pk).exists())

    def test_ultra_can_change_state_and_delete(self):
        ultra = make_user("ultra@test.com", User.Roles.ULTRA, owner=self.owner)
        self.client.force_login(ultra)

        create_record(self.client, self.owner)
        record = Record.objects.get(owner=self.owner)

        response = self.client.post(
            reverse("core:record-status", args=[record.pk]), {"status": "ativo"}
        )
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, "ativo")

        response = self.client.post(
            reverse("core:record-delete", args=[record.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Record.objects.filter(pk=record.pk).exists())

    def test_records_are_scoped_per_organization(self):
        other = make_user("boss2@test.com", User.Roles.ADMIN, is_owner=True)
        self.client.force_login(self.owner)
        record = create_record(self.client, self.owner)

        self.client.force_login(other)
        response = self.client.post(
            reverse("core:record-status", args=[record.pk]), {"status": "ativo"}
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse("core:record-delete", args=[record.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Record.objects.filter(pk=record.pk).exists())
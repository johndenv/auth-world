from django.db import migrations


def set_owner_role_admin(apps, schema_editor):
    User = apps.get_model("auth_service", "User")
    User.objects.filter(is_owner=True).exclude(role="admin").update(role="admin")


def revert_owner_role(apps, schema_editor):
    User = apps.get_model("auth_service", "User")
    User.objects.filter(is_owner=True).update(role="noob")


class Migration(migrations.Migration):

    dependencies = [
        ("auth_service", "0005_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(set_owner_role_admin, revert_owner_role),
    ]
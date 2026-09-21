from django import forms

from .models import Record


class RecordForm(forms.ModelForm):
    """Ação 'Registro': criar um novo nome na lista."""

    class Meta:
        model = Record
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "Digite o nome para registrar..."}
            ),
        }
        labels = {"name": "Nome"}


class RecordStatusForm(forms.ModelForm):
    """Ação 'Estado': alterar pendente/bloqueado/ativo."""

    class Meta:
        model = Record
        fields = ["status"]
        widgets = {
            "status": forms.Select(attrs={"class": "status-select"}),
        }
        labels = {"status": "Status"}
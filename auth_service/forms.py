import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

User = get_user_model()


class LoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Senha incorreta. Tente novamente.",
        "inactive": "Sua conta está inativa.",
    }
    username = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "Seu email"}),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"placeholder": "Sua senha"}),
    )


class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Senha"}),
        label="Senha",
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirmar senha"}),
        label="Confirmar senha",
    )

    country_code = forms.CharField(
        label="DDI",
        initial="55",
        widget=forms.TextInput(attrs={"placeholder": "Ex: 55"}),
    )
    phone_with_ddd = forms.CharField(
        label="Telefone com DDD",
        widget=forms.TextInput(attrs={"placeholder": "Ex: 31997623668"}),
    )

    class Meta:
        model = User
        fields = ["email", "phone"]
        labels = {"email": "E-mail"}
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "Seu melhor email"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("As senhas precisam ser iguais.")

        ddi = cleaned_data.get("country_code", "").strip()
        num_phone = cleaned_data.get("phone_with_ddd", "").strip()

        if ddi and num_phone:
            ddi_limpo = re.sub(r"\D", "", ddi)
            num_limpo = re.sub(r"\D", "", num_phone)
            phone_final = f"{ddi_limpo}{num_limpo}"

            if len(phone_final) < 12 or len(phone_final) > 14:
                raise ValidationError({
                    "phone_with_ddd": "Formato de telefone inválido. Verifique o DDI/DDD e o número."
                })

            cleaned_data["phone"] = phone_final
        else:
            raise ValidationError({
                "phone_with_ddd": "O número de telefone é obrigatório."
            })

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.phone = self.cleaned_data["phone"]
        if commit:
            user.save()
        return user


class SubUserForm(forms.ModelForm):
    """Formulário usado pelo criador da conta para criar novos usuários."""

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Senha"}),
        label="Senha",
    )
    role = forms.ChoiceField(
        # Somente noob, pro e ultra. O cargo admin é exclusivo do criador da conta.
        choices=[
            (value, label)
            for value, label in User.Roles.choices
            if value != User.Roles.ADMIN
        ],
        label="Cargo",
    )

    class Meta:
        model = User
        fields = ["email", "phone", "role"]
        labels = {"email": "E-mail"}
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "Email do usuário"}),
            "phone": forms.TextInput(attrs={"placeholder": "Telefone (opcional)"}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_active = True
        if commit:
            user.save()
        return user


class VerificationCode(forms.Form):
    cod = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"placeholder": "123456"}),
        label="Código de verificação",
    )

    def clean_cod(self):
        cod = self.cleaned_data.get("cod", "").strip()
        if not cod.isdigit():
            raise forms.ValidationError("O código deve conter apenas números.")
        return cod

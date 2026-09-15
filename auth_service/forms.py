from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re

User = get_user_model

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm password!")

    class Meta:
        model = User

        fields = ['email', 'phone', 'password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("The fields must be identical")

        # Captura e formatação dos campos de telefone
        ddi = cleaned_data.get("country_code", "").strip()
        num_phone = cleaned_data.get("phone_with_ddd", "").strip()

        if ddi and num_phone:
            # Remove qualquer caractere que não seja número (parênteses, espaços, hífen)
            ddi_limpo = re.sub(r'\D', '', ddi)
            num_limpo = re.sub(r'\D', '', num_phone)
            
            # Junta os dois no formato final: 5531997623668
            phone_final = f"{ddi_limpo}{num_limpo}"
            
            # Validação simples de tamanho (ex: DDI 2 dígitos + DDD 2 dígitos + número 8 ou 9 dígitos)
            if len(phone_final) < 12 or len(phone_final) > 14:
                raise ValidationError({"phone_with_ddd": "Invalid phone format. Check the area code and the number"})
            
            # Salva o valor final formatado no dicionário para ser usado no save()
            cleaned_data["phone"] = phone_final
        else:
            raise ValidationError({"phone_com_ddd": "The phone number is mandatory"})

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.phone = self.cleaned_data["phone"]
        
        if commit:
            user.save()
        return user

class UserAdminChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'nome', 'phone', 'is_active', 'is_staff')


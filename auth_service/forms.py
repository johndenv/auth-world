from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re

User = get_user_model()

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm password!")

    country_code = forms.CharField(
        label="Country Code (DDI)", 
        initial="55", 
        widget=forms.TextInput(attrs={'placeholder': 'Ex: 55', 'style': 'width: 70px;'})
    )
    phone_with_ddd = forms.CharField(
        label="Phone with DDD", 
        widget=forms.TextInput(attrs={'placeholder': 'Ex: 31997623668'})
    )

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
            raise ValidationError({"phone_with_ddd": "The phone number is mandatory"})

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
        fields = ('email', 'phone', 'is_active', 'is_staff')

class VerificationCode(forms.Form):
    cod = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={'placeholder': '123456'}),
        label="Verification code"
    )

    def clean_cod(self):
        cod = self.cleaned_data.get("cod", "").strip()
        if not cod.isdigit():
            raise forms.ValidationError("O código deve conter apenas números.")
        return cod
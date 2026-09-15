from django.shortcuts import render
from django.views.generic.edit import CreateView
from django.contrib.auth import get_user_model
from django.contrib import messages
from .forms import UserForm
from django.urls import reverse_lazy

User = get_user_model()

class RegisterUser(CreateView):
    template_name = "auth_service/register.html"
    form_class = UserForm
    model = User
    success_message = 'The user has been successfully registered'

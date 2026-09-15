from django.shortcuts import render
from django.views.generic.edit import CreateView
from django.contrib.auth import get_user_model


def get(request):
    return render(request, "auth/register.html")

from django.shortcuts import render
from django.views.generic.edit import CreateView


def get(request):
    return render(request, "auth/register.html")

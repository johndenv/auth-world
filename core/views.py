from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import RecordForm, RecordStatusForm
from .models import Record


def _get_owner(user):
    """Retorna o dono da organização a que o usuário pertence."""
    return user if user.is_owner else user.owner


class WorkAreaView(LoginRequiredMixin, ListView):
    """'Área de trabalho': ações registro, estado e exclusão."""

    model = Record
    template_name = "core/work_area.html"
    context_object_name = "records"
    paginate_by = 20

    def get_queryset(self):
        return Record.objects.filter(owner=_get_owner(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["record_form"] = RecordForm()
        context["status_form"] = RecordStatusForm()
        context["can_change_state"] = user.can_change_state()
        context["can_delete_records"] = user.can_delete_records()
        context["can_manage_users"] = user.can_manage_users()
        return context


class CreateRecordView(LoginRequiredMixin, CreateView):
    """Ação 'Registro': todos os cargos podem criar nomes."""

    model = Record
    form_class = RecordForm
    success_url = reverse_lazy("core:work-area")

    def form_valid(self, form):
        form.instance.owner = _get_owner(self.request.user)
        form.instance.created_by = self.request.user
        self.object = form.save()
        return redirect(self.get_success_url())


class UpdateRecordStatusView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Ação 'Estado': pro, ultra e admin podem alterar o status."""

    model = Record
    form_class = RecordStatusForm
    pk_url_kwarg = "record_id"
    success_url = reverse_lazy("core:work-area")

    def test_func(self):
        return self.request.user.can_change_state()

    def get_queryset(self):
        return Record.objects.filter(owner=_get_owner(self.request.user))

    def form_valid(self, form):
        self.object = form.save()
        return redirect(self.get_success_url())


class DeleteRecordView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Ação 'Exclusão': ultra e admin podem excluir registros."""

    model = Record
    pk_url_kwarg = "record_id"
    success_url = reverse_lazy("core:work-area")

    def test_func(self):
        return self.request.user.can_delete_records()

    def get_queryset(self):
        return Record.objects.filter(owner=_get_owner(self.request.user))
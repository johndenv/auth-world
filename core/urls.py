from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("work-area/", views.WorkAreaView.as_view(), name="work-area"),
    path("records/create/", views.CreateRecordView.as_view(), name="record-create"),
    path(
        "records/<int:record_id>/status/",
        views.UpdateRecordStatusView.as_view(),
        name="record-status",
    ),
    path(
        "records/<int:record_id>/delete/",
        views.DeleteRecordView.as_view(),
        name="record-delete",
    ),
]
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Search
    path("search/", views.global_search, name="global_search"),

    # Timeline note
    path("timeline/add-note/", views.add_note, name="add_note"),

    # Command palette
    path("command/preview/", views.command_preview, name="command_preview"),
    path("command/execute/", views.command_execute, name="command_execute"),

    # Contacts
    path("contacts/", views.contact_list, name="contact_list"),
    path("contacts/new/", views.contact_create, name="contact_create"),
    path("contacts/<int:pk>/", views.contact_detail, name="contact_detail"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact_edit"),
    path("contacts/<int:pk>/delete/", views.contact_delete, name="contact_delete"),

    # Companies
    path("companies/", views.company_list, name="company_list"),
    path("companies/new/", views.company_create, name="company_create"),
    path("companies/<int:pk>/", views.company_detail, name="company_detail"),
    path("companies/<int:pk>/edit/", views.company_edit, name="company_edit"),
    path("companies/<int:pk>/delete/", views.company_delete, name="company_delete"),
    path("companies/<int:pk>/enrich/", views.company_enrich, name="company_enrich"),

    # Deals
    path("deals/", views.deal_list, name="deal_list"),
    path("deals/kanban/", views.deal_kanban, name="deal_kanban"),
    path("deals/new/", views.deal_create, name="deal_create"),
    path("deals/<int:pk>/", views.deal_detail, name="deal_detail"),
    path("deals/<int:pk>/edit/", views.deal_edit, name="deal_edit"),
    path("deals/<int:pk>/delete/", views.deal_delete, name="deal_delete"),
    path("deals/<int:pk>/update-stage/", views.deal_update_stage, name="deal_update_stage"),

    # Activities
    path("activities/", views.activity_list, name="activity_list"),
    path("activities/new/", views.activity_create, name="activity_create"),
    path("activities/<int:pk>/edit/", views.activity_edit, name="activity_edit"),
    path("activities/<int:pk>/delete/", views.activity_delete, name="activity_delete"),

    # Tasks
    path("tasks/", views.task_list, name="task_list"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),

    # V4 — Agent
    path("agent/run/", views.agent_run, name="agent_run"),

    # V4 — Unified Inbox
    path("inbox/", views.unified_inbox, name="unified_inbox"),
    path("inbox/<int:pk>/", views.inbox_message_detail, name="inbox_message_detail"),

    # V4 — Human-in-the-Loop
    path("approvals/", views.suggested_changes, name="suggested_changes"),
    path("approvals/<int:pk>/review/", views.suggested_change_review, name="suggested_change_review"),

    # V4 — Audit Log
    path("audit/", views.audit_log, name="audit_log"),

    # V4 — Voice note
    path("voice-note/process/", views.process_voice_note, name="process_voice_note"),

    # V4 — Leaderboard
    path("leaderboard/", views.leaderboard, name="leaderboard"),
]

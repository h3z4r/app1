import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Company, Contact, Deal, Activity, Task
from .forms import CompanyForm, ContactForm, DealForm, ActivityForm, NoteForm, TaskForm


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    contacts_count = Contact.objects.filter(owner=request.user).count()
    companies_count = Company.objects.filter(owner=request.user).count()
    deals_count = Deal.objects.filter(owner=request.user).count()
    total_value = (
        Deal.objects.filter(owner=request.user, stage="won")
        .aggregate(Sum("value"))["value__sum"] or 0
    )
    deals_by_stage = Deal.objects.filter(owner=request.user).values("stage").annotate(count=Count("id"))
    recent_activities = (
        Activity.objects.filter(owner=request.user)
        .select_related("contact", "deal")[:5]
    )
    recent_deals = (
        Deal.objects.filter(owner=request.user)
        .select_related("contact", "company")[:5]
    )
    my_tasks = (
        Task.objects.filter(owner=request.user)
        .exclude(status="done")
        .select_related("contact", "deal")
        .order_by("due_date")[:10]
    )
    context = {
        "contacts_count": contacts_count,
        "companies_count": companies_count,
        "deals_count": deals_count,
        "total_value": total_value,
        "deals_by_stage": {d["stage"]: d["count"] for d in deals_by_stage},
        "recent_activities": recent_activities,
        "recent_deals": recent_deals,
        "my_tasks": my_tasks,
    }
    return render(request, "crm/dashboard.html", context)


# ---------------------------------------------------------------------------
# Global Search
# ---------------------------------------------------------------------------

@login_required
def global_search(request):
    q = request.GET.get("q", "").strip()
    contacts = companies = deals = []
    if q:
        contacts = Contact.objects.filter(
            owner=request.user
        ).filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        ).select_related("company")[:10]

        companies = Company.objects.filter(
            owner=request.user
        ).filter(
            Q(name__icontains=q) | Q(industry__icontains=q) | Q(email__icontains=q)
        )[:10]

        deals = Deal.objects.filter(
            owner=request.user
        ).filter(
            Q(title__icontains=q)
        ).select_related("contact", "company")[:10]

    return render(request, "crm/search_results.html", {
        "q": q,
        "contacts": contacts,
        "companies": companies,
        "deals": deals,
    })


# ---------------------------------------------------------------------------
# Timeline: add note
# ---------------------------------------------------------------------------

@login_required
@require_POST
def add_note(request):
    form = NoteForm(request.POST)
    if form.is_valid():
        body = form.cleaned_data["body"]
        contact_id = request.POST.get("contact_id")
        company_id = request.POST.get("company_id")
        deal_id = request.POST.get("deal_id")

        activity = Activity(
            type="note",
            subject="Note",
            body=body,
            owner=request.user,
            is_system=False,
        )
        if contact_id:
            activity.contact_id = contact_id
        if company_id:
            activity.company_id = company_id
        if deal_id:
            activity.deal_id = deal_id
        activity.save()
        messages.success(request, "Note added.")

    # Redirect back to where we came from
    return redirect(request.POST.get("next", "/"))


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@login_required
def contact_list(request):
    q = request.GET.get("q", "")
    contacts = Contact.objects.filter(owner=request.user).select_related("company")
    if q:
        contacts = contacts.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    return render(request, "crm/contact_list.html", {"contacts": contacts, "q": q})


@login_required
def contact_detail(request, pk):
    contact = get_object_or_404(Contact, pk=pk, owner=request.user)
    timeline = Activity.objects.filter(contact=contact).select_related("owner").order_by("-created_at")
    note_form = NoteForm()
    return render(request, "crm/contact_detail.html", {
        "contact": contact,
        "timeline": timeline,
        "note_form": note_form,
    })


@login_required
def contact_create(request):
    form = ContactForm(request.POST or None)
    if form.is_valid():
        contact = form.save(commit=False)
        contact.owner = request.user
        contact.save()
        messages.success(request, "Contact created.")
        return redirect("contact_detail", pk=contact.pk)
    return render(request, "crm/contact_form.html", {"form": form, "title": "New Contact"})


@login_required
def contact_edit(request, pk):
    contact = get_object_or_404(Contact, pk=pk, owner=request.user)
    form = ContactForm(request.POST or None, instance=contact)
    if form.is_valid():
        form.save()
        messages.success(request, "Contact updated.")
        return redirect("contact_detail", pk=contact.pk)
    return render(request, "crm/contact_form.html", {"form": form, "title": "Edit Contact"})


@login_required
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk, owner=request.user)
    if request.method == "POST":
        contact.delete()
        messages.success(request, "Contact deleted.")
        return redirect("contact_list")
    return render(request, "crm/confirm_delete.html", {"object": contact, "type": "Contact"})


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

@login_required
def company_list(request):
    q = request.GET.get("q", "")
    companies = Company.objects.filter(owner=request.user)
    if q:
        companies = companies.filter(Q(name__icontains=q) | Q(industry__icontains=q))
    return render(request, "crm/company_list.html", {"companies": companies, "q": q})


@login_required
def company_detail(request, pk):
    company = get_object_or_404(Company, pk=pk, owner=request.user)
    timeline = Activity.objects.filter(company=company).select_related("owner").order_by("-created_at")
    note_form = NoteForm()
    return render(request, "crm/company_detail.html", {
        "company": company,
        "timeline": timeline,
        "note_form": note_form,
    })


@login_required
def company_create(request):
    form = CompanyForm(request.POST or None)
    if form.is_valid():
        company = form.save(commit=False)
        company.owner = request.user
        company.save()
        messages.success(request, "Company created.")
        return redirect("company_detail", pk=company.pk)
    return render(request, "crm/company_form.html", {"form": form, "title": "New Company"})


@login_required
def company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk, owner=request.user)
    form = CompanyForm(request.POST or None, instance=company)
    if form.is_valid():
        form.save()
        messages.success(request, "Company updated.")
        return redirect("company_detail", pk=company.pk)
    return render(request, "crm/company_form.html", {"form": form, "title": "Edit Company"})


@login_required
def company_delete(request, pk):
    company = get_object_or_404(Company, pk=pk, owner=request.user)
    if request.method == "POST":
        action = request.POST.get("action", "nullify")
        if action == "cascade":
            company.contacts.all().delete()
        company.delete()
        messages.success(request, "Company deleted.")
        return redirect("company_list")
    contact_count = company.contacts.count()
    return render(request, "crm/company_confirm_delete.html", {
        "company": company,
        "contact_count": contact_count,
    })


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

@login_required
def deal_list(request):
    q = request.GET.get("q", "")
    stage = request.GET.get("stage", "")
    deals = Deal.objects.filter(owner=request.user).select_related("contact", "company")
    if q:
        deals = deals.filter(Q(title__icontains=q))
    if stage:
        deals = deals.filter(stage=stage)
    return render(request, "crm/deal_list.html", {
        "deals": deals, "q": q, "stage": stage, "stages": Deal.STAGE_CHOICES,
    })


@login_required
def deal_kanban(request):
    deals = Deal.objects.filter(owner=request.user).select_related("contact", "company")

    columns = []
    for key, label in Deal.STAGE_CHOICES:
        stage_deals = [d for d in deals if d.stage == key]
        total = sum(d.value for d in stage_deals)
        columns.append({
            "key": key,
            "label": label,
            "deals": stage_deals,
            "total": total,
            "count": len(stage_deals),
        })

    return render(request, "crm/deal_kanban.html", {"columns": columns})


@login_required
@require_POST
def deal_update_stage(request, pk):
    deal = get_object_or_404(Deal, pk=pk, owner=request.user)
    try:
        data = json.loads(request.body)
        new_stage = data.get("stage")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    valid_stages = [s[0] for s in Deal.STAGE_CHOICES]
    if new_stage not in valid_stages:
        return JsonResponse({"error": "Invalid stage"}, status=400)

    deal.stage = new_stage
    deal.save()
    return JsonResponse({"ok": True, "stage": new_stage})


@login_required
def deal_detail(request, pk):
    deal = get_object_or_404(Deal, pk=pk, owner=request.user)
    timeline = Activity.objects.filter(deal=deal).select_related("owner").order_by("-created_at")
    note_form = NoteForm()
    return render(request, "crm/deal_detail.html", {
        "deal": deal,
        "timeline": timeline,
        "note_form": note_form,
    })


@login_required
def deal_create(request):
    form = DealForm(request.POST or None)
    if form.is_valid():
        deal = form.save(commit=False)
        deal.owner = request.user
        deal.save()
        messages.success(request, "Deal created.")
        return redirect("deal_detail", pk=deal.pk)
    return render(request, "crm/deal_form.html", {"form": form, "title": "New Deal"})


@login_required
def deal_edit(request, pk):
    deal = get_object_or_404(Deal, pk=pk, owner=request.user)
    form = DealForm(request.POST or None, instance=deal)
    if form.is_valid():
        form.save()
        messages.success(request, "Deal updated.")
        return redirect("deal_detail", pk=deal.pk)
    return render(request, "crm/deal_form.html", {"form": form, "title": "Edit Deal"})


@login_required
def deal_delete(request, pk):
    deal = get_object_or_404(Deal, pk=pk, owner=request.user)
    if request.method == "POST":
        deal.delete()
        messages.success(request, "Deal deleted.")
        return redirect("deal_list")
    return render(request, "crm/confirm_delete.html", {"object": deal, "type": "Deal"})


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

@login_required
def activity_list(request):
    activities = Activity.objects.filter(owner=request.user).select_related("contact", "deal")
    return render(request, "crm/activity_list.html", {"activities": activities})


@login_required
def activity_create(request):
    form = ActivityForm(request.POST or None)
    if form.is_valid():
        activity = form.save(commit=False)
        activity.owner = request.user
        activity.save()
        messages.success(request, "Activity logged.")
        return redirect("activity_list")
    return render(request, "crm/activity_form.html", {"form": form, "title": "Log Activity"})


@login_required
def activity_edit(request, pk):
    activity = get_object_or_404(Activity, pk=pk, owner=request.user)
    form = ActivityForm(request.POST or None, instance=activity)
    if form.is_valid():
        form.save()
        messages.success(request, "Activity updated.")
        return redirect("activity_list")
    return render(request, "crm/activity_form.html", {"form": form, "title": "Edit Activity"})


@login_required
def activity_delete(request, pk):
    activity = get_object_or_404(Activity, pk=pk, owner=request.user)
    if request.method == "POST":
        activity.delete()
        messages.success(request, "Activity deleted.")
        return redirect("activity_list")
    return render(request, "crm/confirm_delete.html", {"object": activity, "type": "Activity"})


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@login_required
def task_list(request):
    status_filter = request.GET.get("status", "")
    tasks = Task.objects.filter(owner=request.user).select_related("contact", "deal")
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    return render(request, "crm/task_list.html", {
        "tasks": tasks,
        "status_filter": status_filter,
        "status_choices": Task.STATUS_CHOICES,
    })


@login_required
def task_create(request):
    form = TaskForm(request.POST or None)
    if form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.save()
        messages.success(request, "Task created.")
        return redirect("task_list")
    return render(request, "crm/task_form.html", {"form": form, "title": "New Task"})


@login_required
def task_edit(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    form = TaskForm(request.POST or None, instance=task)
    if form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
        return redirect("task_list")
    return render(request, "crm/task_form.html", {"form": form, "title": "Edit Task"})


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect("task_list")
    return render(request, "crm/confirm_delete.html", {"object": task, "type": "Task"})

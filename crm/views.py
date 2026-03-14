import json
import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Company, Contact, Deal, Activity, Task, AuditLog, SuggestedChange, InboxMessage, AgentRun
from .forms import CompanyForm, ContactForm, DealForm, ActivityForm, NoteForm, TaskForm
from .services.ai_logic import (
    generate_suggestions, parse_command, execute_command,
    enrich_company, extract_domain, suggest_quick_reply,
    process_voice_transcript, compute_user_win_rate, compute_speed_to_lead,
)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    user = request.user
    contacts_count  = Contact.objects.filter(owner=user).count()
    companies_count = Company.objects.filter(owner=user).count()
    deals_count     = Deal.objects.filter(owner=user).count()
    total_value     = (
        Deal.objects.filter(owner=user, stage="won")
        .aggregate(Sum("value"))["value__sum"] or 0
    )
    deals_by_stage = Deal.objects.filter(owner=user).values("stage").annotate(count=Count("id"))
    recent_activities = (
        Activity.objects.filter(owner=user)
        .select_related("contact", "deal")[:5]
    )
    recent_deals = (
        Deal.objects.filter(owner=user)
        .select_related("contact", "company")[:5]
    )
    my_tasks = (
        Task.objects.filter(owner=user)
        .exclude(status="done")
        .select_related("contact", "deal")
        .order_by("due_date")[:10]
    )

    # At-risk deals
    at_risk_deals = (
        Deal.objects.filter(owner=user, at_risk=True)
        .exclude(stage__in=["won", "lost"])
        .select_related("contact", "company")
    )

    # Next Best Action suggestions
    suggestions = generate_suggestions(user)

    # Revenue forecast — 3 past months (won) + 6 future months (expected)
    today = timezone.now().date()
    chart_labels, chart_won, chart_forecast = [], [], []
    for offset in range(-3, 7):
        # First day of month
        m = (today.replace(day=1) + datetime.timedelta(days=32 * offset)).replace(day=1)
        m_end = (m + datetime.timedelta(days=32)).replace(day=1)
        chart_labels.append(m.strftime("%b %Y"))

        if m < today.replace(day=1):
            # Historical: sum of won deals updated in this month
            won = (
                Deal.objects.filter(owner=user, stage="won", updated_at__date__gte=m, updated_at__date__lt=m_end)
                .aggregate(Sum("value"))["value__sum"] or 0
            )
            chart_won.append(float(won))
            chart_forecast.append(None)
        else:
            # Forecast: weighted by close_probability
            open_deals = Deal.objects.filter(
                owner=user, close_date__gte=m, close_date__lt=m_end
            ).exclude(stage__in=["won", "lost"])
            expected = sum(float(d.value) * d.close_probability / 100 for d in open_deals)
            chart_forecast.append(round(expected, 2))
            chart_won.append(None)

    context = {
        "contacts_count":  contacts_count,
        "companies_count": companies_count,
        "deals_count":     deals_count,
        "total_value":     total_value,
        "deals_by_stage":  {d["stage"]: d["count"] for d in deals_by_stage},
        "recent_activities": recent_activities,
        "recent_deals":    recent_deals,
        "my_tasks":        my_tasks,
        "at_risk_deals":   at_risk_deals,
        "suggestions":     suggestions,
        "chart_labels":    json.dumps(chart_labels),
        "chart_won":       json.dumps(chart_won),
        "chart_forecast":  json.dumps(chart_forecast),
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
        contacts  = Contact.objects.filter(owner=request.user).filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        ).select_related("company")[:10]
        companies = Company.objects.filter(owner=request.user).filter(
            Q(name__icontains=q) | Q(industry__icontains=q) | Q(email__icontains=q)
        )[:10]
        deals = Deal.objects.filter(owner=request.user).filter(
            Q(title__icontains=q)
        ).select_related("contact", "company")[:10]
    return render(request, "crm/search_results.html", {"q": q, "contacts": contacts, "companies": companies, "deals": deals})


# ---------------------------------------------------------------------------
# Timeline note
# ---------------------------------------------------------------------------

@login_required
@require_POST
def add_note(request):
    form = NoteForm(request.POST)
    if form.is_valid():
        body = form.cleaned_data["body"]
        activity = Activity(type="note", subject="Note", body=body, owner=request.user, is_system=False)
        for field in ("contact_id", "company_id", "deal_id"):
            val = request.POST.get(field.replace("_id", "") + "_id")
            if val:
                setattr(activity, field, val)
        activity.save()
        messages.success(request, "Note added.")
    return redirect(request.POST.get("next", "/"))


# ---------------------------------------------------------------------------
# Company enrichment
# ---------------------------------------------------------------------------

@login_required
@require_POST
def company_enrich(request, pk):
    company = get_object_or_404(Company, pk=pk, owner=request.user)
    domain = request.POST.get("domain") or extract_domain(company.website)
    if not domain:
        return JsonResponse({"error": "No domain provided and no website set on company."}, status=400)

    data = enrich_company(domain)
    updated = {}
    if data.get("industry") and not company.industry:
        company.industry = data["industry"]
        updated["industry"] = data["industry"]
    if data.get("employee_count") and not company.employee_count:
        company.employee_count = data["employee_count"]
        updated["employee_count"] = data["employee_count"]
    if data.get("linkedin_url") and not company.linkedin_url:
        company.linkedin_url = data["linkedin_url"]
        updated["linkedin_url"] = data["linkedin_url"]

    if updated:
        company.save()

    return JsonResponse({"ok": True, "updated": updated, "domain": domain})


# ---------------------------------------------------------------------------
# Command palette
# ---------------------------------------------------------------------------

@login_required
def command_preview(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"message": "", "action": None})
    result = parse_command(q, request.user)
    return JsonResponse(result)


@login_required
@require_POST
def command_execute(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    result = execute_command(data, request.user)
    return JsonResponse(result)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@login_required
def contact_list(request):
    q = request.GET.get("q", "")
    contacts = Contact.objects.filter(owner=request.user).select_related("company")
    if q:
        contacts = contacts.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    return render(request, "crm/contact_list.html", {"contacts": contacts, "q": q})


@login_required
def contact_detail(request, pk):
    contact = get_object_or_404(Contact, pk=pk, owner=request.user)
    timeline = Activity.objects.filter(contact=contact).select_related("owner").order_by("-created_at")
    return render(request, "crm/contact_detail.html", {"contact": contact, "timeline": timeline, "note_form": NoteForm()})


@login_required
def contact_create(request):
    form = ContactForm(request.POST or None)
    if form.is_valid():
        c = form.save(commit=False)
        c.owner = request.user
        c.save()
        messages.success(request, "Contact created.")
        return redirect("contact_detail", pk=c.pk)
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
    return render(request, "crm/company_detail.html", {"company": company, "timeline": timeline, "note_form": NoteForm()})


@login_required
def company_create(request):
    form = CompanyForm(request.POST or None)
    if form.is_valid():
        c = form.save(commit=False)
        c.owner = request.user
        c.save()
        messages.success(request, "Company created.")
        return redirect("company_detail", pk=c.pk)
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
        if request.POST.get("action") == "cascade":
            company.contacts.all().delete()
        company.delete()
        messages.success(request, "Company deleted.")
        return redirect("company_list")
    return render(request, "crm/company_confirm_delete.html", {"company": company, "contact_count": company.contacts.count()})


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
    return render(request, "crm/deal_list.html", {"deals": deals, "q": q, "stage": stage, "stages": Deal.STAGE_CHOICES})


@login_required
def deal_kanban(request):
    deals = Deal.objects.filter(owner=request.user).select_related("contact", "company")
    columns = []
    for key, label in Deal.STAGE_CHOICES:
        stage_deals = [d for d in deals if d.stage == key]
        total = sum(d.value for d in stage_deals)
        columns.append({"key": key, "label": label, "deals": stage_deals, "total": total, "count": len(stage_deals)})
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
    valid = [s[0] for s in Deal.STAGE_CHOICES]
    if new_stage not in valid:
        return JsonResponse({"error": "Invalid stage"}, status=400)
    deal.stage = new_stage
    deal.save()
    return JsonResponse({"ok": True, "stage": new_stage})


@login_required
def deal_detail(request, pk):
    deal = get_object_or_404(Deal, pk=pk, owner=request.user)
    timeline = Activity.objects.filter(deal=deal).select_related("owner").order_by("-created_at")
    return render(request, "crm/deal_detail.html", {"deal": deal, "timeline": timeline, "note_form": NoteForm()})


@login_required
def deal_create(request):
    initial = {}
    # Support pre-fill from command palette
    if request.GET.get("company_id"):
        initial["company"] = request.GET["company_id"]
    form = DealForm(request.POST or None, initial=initial)
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
        a = form.save(commit=False)
        a.owner = request.user
        a.save()
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
    return render(request, "crm/task_list.html", {"tasks": tasks, "status_filter": status_filter, "status_choices": Task.STATUS_CHOICES})


@login_required
def task_create(request):
    # Support pre-fill from suggestions / command palette
    initial = {}
    if request.GET.get("contact"):
        initial["contact"] = request.GET["contact"]
    if request.GET.get("deal"):
        initial["deal"] = request.GET["deal"]
    if request.GET.get("prefill_title"):
        initial["title"] = request.GET["prefill_title"]

    form = TaskForm(request.POST or None, initial=initial)
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


# ---------------------------------------------------------------------------
# V4 — Autonomous Agent trigger
# ---------------------------------------------------------------------------

@login_required
@require_POST
def agent_run(request):
    from .agents.sales_agent import run_sales_agent
    agent_run_obj = AgentRun.objects.create(owner=request.user, status="running")
    try:
        result = run_sales_agent(request.user)
        total = len(result["actions"]) + len(result["suggested"])
        agent_run_obj.status = "completed"
        agent_run_obj.actions_taken = total
        agent_run_obj.summary = "\n".join(result["actions"] + result["suggested"])
        agent_run_obj.save()
        messages.success(request, f"Agent completed — {total} action(s) taken or queued.")
    except Exception as e:
        agent_run_obj.status = "error"
        agent_run_obj.summary = str(e)
        agent_run_obj.save()
        messages.error(request, f"Agent error: {e}")
    return redirect("dashboard")


# ---------------------------------------------------------------------------
# V4 — Unified Inbox
# ---------------------------------------------------------------------------

@login_required
def unified_inbox(request):
    source_filter = request.GET.get("source", "")
    msgs = InboxMessage.objects.filter(owner=request.user).select_related("contact")
    if source_filter:
        msgs = msgs.filter(source=source_filter)
    unread_count = InboxMessage.objects.filter(owner=request.user, read=False).count()
    return render(request, "crm/unified_inbox.html", {
        "messages": msgs,
        "source_filter": source_filter,
        "unread_count": unread_count,
        "source_choices": InboxMessage.SOURCE_CHOICES,
    })


@login_required
def inbox_message_detail(request, pk):
    msg = get_object_or_404(InboxMessage, pk=pk, owner=request.user)
    if not msg.read:
        msg.read = True
        msg.save(update_fields=["read"])
    quick_replies = []
    if msg.direction == "inbound":
        name = msg.contact.first_name if msg.contact else "there"
        quick_replies = suggest_quick_reply(msg.body, name)
    return render(request, "crm/inbox_message_detail.html", {
        "msg": msg,
        "quick_replies": quick_replies,
    })


# ---------------------------------------------------------------------------
# V4 — Human-in-the-Loop approval queue
# ---------------------------------------------------------------------------

@login_required
def suggested_changes(request):
    pending = SuggestedChange.objects.filter(owner=request.user, status="pending").select_related("deal")
    reviewed = SuggestedChange.objects.filter(owner=request.user).exclude(status="pending").select_related("deal")[:20]
    return render(request, "crm/suggested_changes.html", {
        "pending": pending,
        "reviewed": reviewed,
    })


@login_required
@require_POST
def suggested_change_review(request, pk):
    change = get_object_or_404(SuggestedChange, pk=pk, owner=request.user, status="pending")
    action = request.POST.get("action")  # "approve" or "reject"

    if action == "approve":
        if change.change_type == "stage_change":
            change.deal.stage = change.suggested_value
            change.deal.save()
            Activity.objects.create(
                type="stage_change",
                subject=f"Stage changed to {change.suggested_value} (approved suggestion)",
                deal=change.deal,
                owner=request.user,
                is_system=True,
            )
            AuditLog.objects.create(
                source="user",
                action="approved_suggestion",
                object_type="deal",
                object_id=change.deal.pk,
                object_str=str(change.deal),
                detail=f"User approved AI suggestion: {change.current_value} → {change.suggested_value}.",
                user=request.user,
            )
        change.status = "approved"
        messages.success(request, f'Approved: moved "{change.deal}" to {change.suggested_value}.')
    elif action == "reject":
        change.status = "rejected"
        AuditLog.objects.create(
            source="user",
            action="rejected_suggestion",
            object_type="deal",
            object_id=change.deal.pk,
            object_str=str(change.deal),
            detail=f"User rejected AI suggestion: {change.current_value} → {change.suggested_value}.",
            user=request.user,
        )
        messages.info(request, f'Rejected suggestion for "{change.deal}".')
    else:
        messages.error(request, "Invalid action.")
        return redirect("suggested_changes")

    change.reviewed_at = timezone.now()
    change.save()
    return redirect("suggested_changes")


# ---------------------------------------------------------------------------
# V4 — Audit Log
# ---------------------------------------------------------------------------

@login_required
def audit_log(request):
    logs = AuditLog.objects.filter(user=request.user).select_related("user")[:200]
    return render(request, "crm/audit_log.html", {"logs": logs})


# ---------------------------------------------------------------------------
# V4 — Voice note processing
# ---------------------------------------------------------------------------

@login_required
@require_POST
def process_voice_note(request):
    transcript = request.POST.get("transcript", "").strip()
    deal_id = request.POST.get("deal_id")
    contact_id = request.POST.get("contact_id")

    if not transcript:
        return JsonResponse({"error": "No transcript provided."}, status=400)

    parsed = process_voice_transcript(transcript)

    activity = Activity.objects.create(
        type="voice_note",
        subject="Voice Note",
        body=parsed["summary"],
        transcript=transcript,
        sentiment=parsed["sentiment"],
        deal_id=deal_id or None,
        contact_id=contact_id or None,
        owner=request.user,
        is_system=False,
    )
    return JsonResponse({
        "ok": True,
        "activity_id": activity.pk,
        "sentiment": parsed["sentiment"],
        "detected_actions": parsed["detected_actions"],
        "summary": parsed["summary"],
    })


# ---------------------------------------------------------------------------
# V4 — Leaderboard (win rate + speed to lead)
# ---------------------------------------------------------------------------

@login_required
def leaderboard(request):
    from django.contrib.auth.models import User
    users = User.objects.filter(is_active=True)
    board = []
    for u in users:
        win_rate = compute_user_win_rate(u)
        speed = compute_speed_to_lead(u)
        won_count = Deal.objects.filter(owner=u, stage="won").count()
        lost_count = Deal.objects.filter(owner=u, stage="lost").count()
        board.append({
            "user": u,
            "win_rate": win_rate,
            "win_rate_pct": round(win_rate * 100, 1),
            "speed_to_lead": speed,
            "won": won_count,
            "lost": lost_count,
        })
    board.sort(key=lambda x: x["win_rate"], reverse=True)
    return render(request, "crm/leaderboard.html", {"board": board})

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from .models import Company, Contact, Deal, Activity
from .forms import CompanyForm, ContactForm, DealForm, ActivityForm


@login_required
def dashboard(request):
    contacts_count = Contact.objects.filter(owner=request.user).count()
    companies_count = Company.objects.filter(owner=request.user).count()
    deals_count = Deal.objects.filter(owner=request.user).count()
    total_value = Deal.objects.filter(owner=request.user, stage="won").aggregate(Sum("value"))["value__sum"] or 0
    deals_by_stage = Deal.objects.filter(owner=request.user).values("stage").annotate(count=Count("id"))
    recent_activities = Activity.objects.filter(owner=request.user).select_related("contact", "deal")[:5]
    recent_deals = Deal.objects.filter(owner=request.user).select_related("contact", "company")[:5]
    context = {
        "contacts_count": contacts_count,
        "companies_count": companies_count,
        "deals_count": deals_count,
        "total_value": total_value,
        "deals_by_stage": {d["stage"]: d["count"] for d in deals_by_stage},
        "recent_activities": recent_activities,
        "recent_deals": recent_deals,
    }
    return render(request, "crm/dashboard.html", context)


# --- Contact Views ---

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
    return render(request, "crm/contact_detail.html", {"contact": contact})


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


# --- Company Views ---

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
    return render(request, "crm/company_detail.html", {"company": company})


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
        company.delete()
        messages.success(request, "Company deleted.")
        return redirect("company_list")
    return render(request, "crm/confirm_delete.html", {"object": company, "type": "Company"})


# --- Deal Views ---

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
def deal_detail(request, pk):
    deal = get_object_or_404(Deal, pk=pk, owner=request.user)
    return render(request, "crm/deal_detail.html", {"deal": deal})


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


# --- Activity Views ---

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

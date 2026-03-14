"""
AI / business-logic service layer for CRM v3.

All "smart" logic lives here so you can swap in a real LLM API later
by changing only this file — no view or signal code needs to change.
"""

import re
import random
import datetime
from django.utils import timezone
from django.db.models import Q

# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------

RISK_KEYWORDS = {
    "cancel", "cancelled", "cancelling",
    "expensive", "too costly", "overpriced",
    "unhappy", "frustrated", "disappointed",
    "not interested", "pass", "no thanks",
    "competitor", "going with another",
    "worried", "concern", "concerned",
    "delay", "hold off", "pause",
}

POSITIVE_KEYWORDS = {
    "excited", "great", "love it", "perfect",
    "agreed", "moving forward", "let's do it",
    "approved", "signed", "yes", "absolutely",
    "excellent", "happy", "impressed", "looks good",
}

# Stage → base closing probability (%)
STAGE_PROBABILITY = {
    "lead": 10,
    "qualified": 25,
    "proposal": 45,
    "negotiation": 70,
    "won": 100,
    "lost": 0,
}

# Mock enrichment database for known domains
DOMAIN_ENRICHMENT = {
    "google.com":     {"industry": "Technology",           "employee_count": 156_000, "linkedin_url": "https://linkedin.com/company/google"},
    "apple.com":      {"industry": "Consumer Electronics", "employee_count": 164_000, "linkedin_url": "https://linkedin.com/company/apple"},
    "amazon.com":     {"industry": "E-Commerce / Cloud",   "employee_count": 1_500_000,"linkedin_url": "https://linkedin.com/company/amazon"},
    "microsoft.com":  {"industry": "Technology",           "employee_count": 221_000, "linkedin_url": "https://linkedin.com/company/microsoft"},
    "meta.com":       {"industry": "Social Media",         "employee_count": 67_000,  "linkedin_url": "https://linkedin.com/company/meta"},
    "salesforce.com": {"industry": "CRM / SaaS",           "employee_count": 79_000,  "linkedin_url": "https://linkedin.com/company/salesforce"},
    "hubspot.com":    {"industry": "Marketing / SaaS",     "employee_count": 7_400,   "linkedin_url": "https://linkedin.com/company/hubspot"},
    "pipedrive.com":  {"industry": "CRM / SaaS",           "employee_count": 1_000,   "linkedin_url": "https://linkedin.com/company/pipedrive"},
    "stripe.com":     {"industry": "Fintech",              "employee_count": 8_000,   "linkedin_url": "https://linkedin.com/company/stripe"},
    "shopify.com":    {"industry": "E-Commerce",           "employee_count": 11_000,  "linkedin_url": "https://linkedin.com/company/shopify"},
    "slack.com":      {"industry": "Collaboration / SaaS", "employee_count": 2_500,   "linkedin_url": "https://linkedin.com/company/slack"},
    "notion.so":      {"industry": "Productivity / SaaS",  "employee_count": 600,     "linkedin_url": "https://linkedin.com/company/notion"},
    "openai.com":     {"industry": "Artificial Intelligence","employee_count": 3_000,  "linkedin_url": "https://linkedin.com/company/openai"},
}

_MOCK_INDUSTRIES = [
    "Technology", "Finance", "Healthcare", "Retail",
    "Manufacturing", "Education", "Consulting", "Legal",
    "Real Estate", "Media & Entertainment",
]
_MOCK_SIZES = [10, 25, 50, 100, 250, 500, 1_000, 5_000]


# ---------------------------------------------------------------------------
# Health Score
# ---------------------------------------------------------------------------

def compute_health_score(deal):
    """
    Returns an integer 0–100 representing deal health.

    Factors (see V3 proposal for formula):
      + Recency of last manual activity
      + Contact linked
      + Past won deals from same company
      - at_risk flag
    """
    score = 50

    # Factor 1: days since last manual activity on the deal
    last = deal.activities.filter(is_system=False).order_by("-created_at").first()
    if last:
        days = (timezone.now() - last.created_at).days
        if days < 3:
            score += 20
        elif days < 7:
            score += 10
        elif days < 14:
            score += 0
        elif days < 30:
            score -= 10
        else:
            score -= 25
    else:
        score -= 30  # never touched

    # Factor 2: contact linked
    if deal.contact_id:
        score += 10

    # Factor 3: past won deals from the same company
    if deal.company_id:
        from ..models import Deal as DealModel
        won = (
            DealModel.objects
            .filter(company_id=deal.company_id, stage="won")
            .exclude(pk=deal.pk)
            .count()
        )
        score += min(won * 10, 20)

    # Factor 4: at-risk penalty
    if deal.at_risk:
        score -= 20

    return max(0, min(100, score))


def compute_close_probability(deal, health_score=None):
    """
    Returns 0–100 %.
    Won → 100, Lost → 0, others blended from stage base + health.
    """
    if deal.stage == "won":
        return 100
    if deal.stage == "lost":
        return 0

    if health_score is None:
        health_score = deal.health_score

    base = STAGE_PROBABILITY.get(deal.stage, 10)
    # 70 % stage weight, 30 % health influence
    prob = int(base * 0.7 + (health_score / 100 * base) * 0.3)
    return max(1, min(99, prob))


# ---------------------------------------------------------------------------
# Sentiment analysis
# ---------------------------------------------------------------------------

def analyze_sentiment(text):
    """
    Keyword-based sentiment: 'positive', 'neutral', or 'concerned'.
    Replace body with an LLM call when ready.
    """
    if not text:
        return "neutral"

    t = text.lower()
    risk_hits = sum(1 for kw in RISK_KEYWORDS if kw in t)
    pos_hits  = sum(1 for kw in POSITIVE_KEYWORDS if kw in t)

    if risk_hits > 0 and risk_hits >= pos_hits:
        return "concerned"
    if pos_hits > 0:
        return "positive"
    return "neutral"


def check_at_risk(text):
    """Returns True if text contains any risk keyword."""
    if not text:
        return False
    t = text.lower()
    return any(kw in t for kw in RISK_KEYWORDS)


# ---------------------------------------------------------------------------
# Data enrichment (mock — swap for Clearbit / Apollo later)
# ---------------------------------------------------------------------------

def extract_domain(url):
    """Extract bare domain from a URL string."""
    if not url:
        return ""
    from urllib.parse import urlparse
    if "://" not in url:
        url = "https://" + url
    netloc = urlparse(url).netloc
    return netloc.replace("www.", "").lower()


def enrich_company(domain):
    """
    Return enrichment dict for a domain.
    Known domains return real-ish data; others get plausible mocks.
    Swap this function body for a real API call later.
    """
    domain = domain.lower().strip()

    if domain in DOMAIN_ENRICHMENT:
        return DOMAIN_ENRICHMENT[domain]

    # Generic mock
    slug = domain.split(".")[0]
    return {
        "industry": random.choice(_MOCK_INDUSTRIES),
        "employee_count": random.choice(_MOCK_SIZES),
        "linkedin_url": f"https://linkedin.com/company/{slug}",
    }


# ---------------------------------------------------------------------------
# Next Best Action suggestions
# ---------------------------------------------------------------------------

def generate_suggestions(user):
    """
    Returns a list (max 6) of suggestion dicts:
      { icon, message, action_label, action_url }
    """
    from ..models import Contact, Deal

    suggestions = []
    now = timezone.now()

    # 1. Contacts not contacted in 10+ days
    contacts = (
        Contact.objects
        .filter(owner=user)
        .prefetch_related("activities")[:50]
    )
    for contact in contacts:
        last = contact.activities.filter(is_system=False).order_by("-created_at").first()
        if last:
            days = (now - last.created_at).days
            if days >= 10:
                suggestions.append({
                    "icon": "📞",
                    "message": f"You haven't spoken to {contact.full_name} in {days} days. Send a follow-up?",
                    "action_label": "Create Task",
                    "action_url": f"/tasks/new/?contact={contact.pk}&prefill_title=Follow+up+with+{contact.first_name}",
                })
        if len(suggestions) >= 2:
            break

    # 2. Negotiation deals with no open task
    for deal in Deal.objects.filter(owner=user, stage="negotiation").prefetch_related("tasks")[:10]:
        if not deal.tasks.exclude(status="done").exists():
            suggestions.append({
                "icon": "⚠️",
                "message": f'Deal "{deal.title}" is in Negotiation but has no open task. Set one?',
                "action_label": "Create Task",
                "action_url": f"/tasks/new/?deal={deal.pk}&prefill_title=Follow+up+on+{deal.title}",
            })

    # 3. At-risk deals
    for deal in Deal.objects.filter(owner=user, at_risk=True).exclude(stage__in=["won", "lost"])[:3]:
        suggestions.append({
            "icon": "🚨",
            "message": f'Deal "{deal.title}" is flagged At Risk based on recent notes. Review it?',
            "action_label": "View Deal",
            "action_url": f"/deals/{deal.pk}/",
        })

    # 4. Low health score
    for deal in Deal.objects.filter(owner=user, health_score__lt=30).exclude(stage__in=["won", "lost"])[:2]:
        suggestions.append({
            "icon": "📉",
            "message": f'Deal "{deal.title}" has a low health score ({deal.health_score}/100). Time to act?',
            "action_label": "View Deal",
            "action_url": f"/deals/{deal.pk}/",
        })

    return suggestions[:6]


# ---------------------------------------------------------------------------
# Command palette parser
# ---------------------------------------------------------------------------

def parse_command(text, user):
    """
    Parse a natural-language command string.
    Returns a dict:
      { "action": str, "data": dict, "message": str }
      or { "error": str }
    """
    from ..models import Contact, Company

    t = text.strip()
    tl = t.lower()

    # ── Pattern: add/create $X deal to/for [Company] ──────────────────────
    m = re.search(
        r"(?:add|create).*?\$?([\d,]+(?:\.?\d+)?k?)\s*(?:deal|opportunity).*?(?:to|for|with)\s+(.+)",
        tl,
    )
    if m:
        raw_val = m.group(1).replace(",", "")
        value = float(raw_val.replace("k", "")) * (1000 if "k" in raw_val else 1)
        company_name = m.group(2).strip().rstrip(".")
        company = Company.objects.filter(owner=user, name__icontains=company_name).first()
        return {
            "action": "create_deal",
            "data": {
                "title": f"Deal with {company_name.title()}",
                "value": value,
                "company_id": company.pk if company else None,
                "company_name": company_name,
                "stage": "lead",
            },
            "message": f"Create a ${value:,.0f} deal"
                       + (f" linked to {company.name}" if company else f" (company '{company_name}' not found — deal will be unlinked)"),
        }

    # ── Pattern: remind me to call/email [Name] tomorrow/today ────────────
    m = re.search(
        r"remind.*?(?:call|email|contact|follow.?up with?)\s+([a-zA-Z ]+?)(?:\s+(tomorrow|today|in \d+ days?))?[.!?]?$",
        tl,
    )
    if m:
        name = m.group(1).strip()
        when_str = (m.group(2) or "tomorrow").strip()
        contact = (
            Contact.objects
            .filter(owner=user)
            .filter(Q(first_name__icontains=name) | Q(last_name__icontains=name))
            .first()
        )
        today = timezone.now().date()
        if when_str == "today":
            due = today
        elif re.match(r"in (\d+) days?", when_str):
            days = int(re.search(r"\d+", when_str).group())
            due = today + datetime.timedelta(days=days)
        else:
            due = today + datetime.timedelta(days=1)

        return {
            "action": "create_task",
            "data": {
                "title": f"Call {name.title()}",
                "contact_id": contact.pk if contact else None,
                "contact_name": name,
                "due_date": str(due),
            },
            "message": f"Create task: Call {name.title()}"
                       + (f" (linked to {contact.full_name})" if contact else " (contact not found)")
                       + f" — due {due}",
        }

    # ── Pattern: go to / show / open [section] ────────────────────────────
    m = re.search(
        r"(?:go to|show|open|view)\s+(deals?|kanban|contacts?|compan(?:y|ies)|tasks?|dashboard|activities)",
        tl,
    )
    if m:
        dest = m.group(1)
        url_map = {
            "deal": "/deals/", "deals": "/deals/", "kanban": "/deals/kanban/",
            "contact": "/contacts/", "contacts": "/contacts/",
            "company": "/companies/", "companies": "/companies/",
            "task": "/tasks/", "tasks": "/tasks/",
            "activity": "/activities/", "activities": "/activities/",
            "dashboard": "/",
        }
        url = url_map.get(dest, "/")
        return {"action": "navigate", "data": {"url": url}, "message": f"Navigate to {dest}"}

    return {
        "error": f'Couldn\'t parse "{t}". '
                 'Try: "Add $5000 deal to Acme Corp", '
                 '"Remind me to call John tomorrow", '
                 '"Go to Kanban"'
    }


def execute_command(action_data, user):
    """
    Execute a parsed command. Returns { "ok": True, "redirect": url }
    or { "ok": False, "error": msg }.
    """
    from ..models import Deal, Task

    action = action_data.get("action")
    data = action_data.get("data", {})

    if action == "create_deal":
        deal = Deal.objects.create(
            title=data.get("title", "New Deal"),
            value=data.get("value", 0),
            company_id=data.get("company_id"),
            stage=data.get("stage", "lead"),
            owner=user,
        )
        return {"ok": True, "redirect": f"/deals/{deal.pk}/"}

    if action == "create_task":
        raw_due = data.get("due_date")
        due = datetime.date.fromisoformat(raw_due) if raw_due else None
        task = Task.objects.create(
            title=data.get("title", "New Task"),
            contact_id=data.get("contact_id"),
            due_date=due,
            owner=user,
        )
        return {"ok": True, "redirect": "/tasks/"}

    if action == "navigate":
        return {"ok": True, "redirect": data.get("url", "/")}

    return {"ok": False, "error": "Unknown action"}

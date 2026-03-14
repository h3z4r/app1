"""
Autonomous Sales Agent — crm/agents/sales_agent.py

Orchestrates background CRM tasks without human intervention,
except when human-in-the-loop rules apply (high-value deals > $50k).

Run via management command:  python manage.py run_agent
Trigger from UI:             POST /agent/run/
"""

from datetime import timedelta
from django.utils import timezone

HIGH_VALUE_THRESHOLD = 50_000   # USD — above this, require human approval
FOLLOWUP_OVERDUE_DAYS = 7       # days since last activity → draft follow-up
STALE_DAYS = 30                 # days of silence → move to Nurture


# ---------------------------------------------------------------------------
# Email drafter
# ---------------------------------------------------------------------------

def draft_followup_email(deal, last_activity=None):
    """
    Generate a personalised follow-up email body based on
    the last activity's sentiment. Returns plain-text string.
    """
    name = deal.contact.first_name if deal.contact else "there"
    title = deal.title
    sentiment = (last_activity.sentiment if last_activity else "") or "neutral"

    if sentiment == "concerned":
        return (
            f"Hi {name},\n\n"
            f"I wanted to personally follow up regarding {title}. "
            f"I know you've shared some concerns and I want to make sure we address every one of them.\n\n"
            f"Could we schedule a 20-minute call this week? "
            f"I'm confident we can find an approach that works perfectly for you.\n\n"
            f"Looking forward to hearing from you.\n\nBest regards"
        )
    elif sentiment == "positive":
        return (
            f"Hi {name},\n\n"
            f"It was great connecting on {title}! "
            f"I wanted to keep the energy going and confirm our next steps.\n\n"
            f"I can have everything ready within 24 hours of your go-ahead — "
            f"just say the word!\n\nBest regards"
        )
    else:
        return (
            f"Hi {name},\n\n"
            f"I hope you're doing well. I'm following up on {title} "
            f"and wanted to check in to see if you have any questions "
            f"or need any additional information from my side.\n\n"
            f"Please don't hesitate to reach out — I'm here to help.\n\nBest regards"
        )


# ---------------------------------------------------------------------------
# Main agent runner
# ---------------------------------------------------------------------------

def run_sales_agent(user):
    """
    Scan all deals for this user and take autonomous actions.

    Returns:
        {
            "actions":   [str, ...]   # completed autonomously
            "suggested": [str, ...]   # queued for human approval
            "errors":    [str, ...]
        }
    """
    from ..models import Deal, Activity, AuditLog, SuggestedChange

    result = {"actions": [], "suggested": [], "errors": []}
    now = timezone.now()

    # ── 1. Qualified deals with overdue follow-ups ──────────────────────
    qualified = Deal.objects.filter(
        owner=user, stage="qualified"
    ).prefetch_related("activities", "contact")

    for deal in qualified:
        last = deal.activities.filter(is_system=False).order_by("-created_at").first()
        days_since = (now - (last.created_at if last else deal.created_at)).days

        if days_since < FOLLOWUP_OVERDUE_DAYS:
            continue

        # Skip if we already drafted one in the last 3 days
        if deal.activities.filter(
            subject__startswith="[DRAFT]",
            created_at__gte=now - timedelta(days=3),
        ).exists():
            continue

        draft_body = draft_followup_email(deal, last)
        Activity.objects.create(
            type="email",
            subject=f"[DRAFT] Follow-up: {deal.title}",
            body=draft_body,
            deal=deal,
            contact=deal.contact,
            owner=user,
            is_system=True,
        )
        AuditLog.objects.create(
            source="ai_agent",
            action="draft_email_created",
            object_type="deal",
            object_id=deal.pk,
            object_str=str(deal),
            detail=f"Drafted follow-up email. Last contact: {days_since} days ago. Sentiment: {last.sentiment if last else 'N/A'}.",
            user=user,
        )
        result["actions"].append(
            f"📧 Drafted follow-up email for \"{deal.title}\" ({days_since}d since last contact)"
        )

    # ── 2. Move stale deals to Nurture ──────────────────────────────────
    stale_cutoff = now - timedelta(days=STALE_DAYS)
    active_deals = Deal.objects.filter(
        owner=user
    ).exclude(stage__in=["won", "lost", "nurture"])

    for deal in active_deals:
        last = deal.activities.order_by("-created_at").first()
        is_stale = not last or last.created_at < stale_cutoff
        if not is_stale:
            continue

        if deal.is_high_value:
            # Human-in-the-loop: create a suggestion, do NOT act
            _, created = SuggestedChange.objects.get_or_create(
                deal=deal,
                change_type="stage_change",
                status="pending",
                defaults={
                    "current_value": deal.stage,
                    "suggested_value": "nurture",
                    "reason": (
                        f"No activity for {STALE_DAYS}+ days. "
                        f"High-value deal (${float(deal.value):,.0f}) — "
                        f"requires your approval before moving to Nurture."
                    ),
                    "owner": user,
                },
            )
            if created:
                AuditLog.objects.create(
                    source="ai_agent",
                    action="suggested_stage_change",
                    object_type="deal",
                    object_id=deal.pk,
                    object_str=str(deal),
                    detail=f"Suggested Nurture (high-value deal, human approval required).",
                    user=user,
                )
                result["suggested"].append(
                    f"⚠️ Queued for your approval: move \"{deal.title}\" to Nurture "
                    f"(high-value ${float(deal.value):,.0f})"
                )
        else:
            old_stage = deal.stage
            deal.stage = "nurture"
            deal.save()
            Activity.objects.create(
                type="stage_change",
                subject=f"🤖 Agent: moved to Nurture (no activity for {STALE_DAYS}+ days)",
                deal=deal,
                owner=user,
                is_system=True,
            )
            AuditLog.objects.create(
                source="ai_agent",
                action="stage_changed",
                object_type="deal",
                object_id=deal.pk,
                object_str=str(deal),
                detail=f"Stage changed '{old_stage}' → 'nurture' (stale deal, autonomous action).",
                user=user,
            )
            result["actions"].append(
                f"📦 Moved stale deal \"{deal.title}\" to Nurture (was: {old_stage})"
            )

    return result

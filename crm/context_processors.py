def agent_status(request):
    """Inject agent status and pending-approval count into every template."""
    if not request.user.is_authenticated:
        return {}
    from .models import AgentRun, SuggestedChange
    last_run = AgentRun.objects.filter(owner=request.user).order_by("-ran_at").first()
    pending_count = SuggestedChange.objects.filter(
        owner=request.user, status="pending"
    ).count()
    return {
        "agent_last_run": last_run,
        "pending_approvals_count": pending_count,
    }

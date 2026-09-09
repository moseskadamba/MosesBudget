from django.utils import timezone
from django.conf import settings
from .models import UserProfile

def global_tracker_context(request):
    """
    Injects database-validated timezone preferences globally into the app context.
    """
    # Default to global settings.py baseline config if user is browsing unauthenticated pages
    user_tz_name = settings.TIME_ZONE
    
    if request.user.is_authenticated:
        try:
            # Query the user's permanent profile record
            profile = request.user.profile
            user_tz_name = profile.timezone
        except UserProfile.DoesNotExist:
            # Safe recovery if user profile wasn't constructed by signals yet
            pass

    # Activate the target zone within Django's engine for this request lifecycle
    try:
        timezone.activate(user_tz_name)
        active_date = timezone.localdate()
    except Exception:
        timezone.activate(settings.TIME_ZONE)
        user_tz_name = settings.TIME_ZONE
        active_date = timezone.localdate()

    return {
        'timezone_name': user_tz_name,
        'today': active_date
    }
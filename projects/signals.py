"""What other apps may react to, so projects never imports them."""
from django.dispatch import Signal

project_abandoned = Signal()      # sent by the admin's Abandon action, inside its transaction, with `project=` (the saved, abandoned project)

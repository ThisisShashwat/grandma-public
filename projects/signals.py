"""What other apps may react to, so projects never imports them."""
from django.dispatch import Signal

project_abandoned = Signal()      # sent by the admin's Abandon action, inside its transaction, with `project=` (the saved, abandoned project)
project_takedown = Signal()       # sent by the admin's Take down action, with `project=` and `by=` (the staff user); each receiver answers with how many things it took down

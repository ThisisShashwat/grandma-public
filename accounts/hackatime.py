"""THE SEAM for Hackatime. Nothing in this project talks to Hackatime yet, on purpose: it involves personal information and
the owner wants to be there when it is built.

Where it plugs in, when the time comes:
  1. Set AVAILABLE = True once the connection flow exists.
  2. accounts/script.py, the "hackatime" step: replace the greyed-out button (`Say.disabled`) with a link to the connect
     flow, and make "Go on" wait until `Profile.hackatime_connected` is True.
  3. The connect flow's callback sets `Profile.hackatime_connected = True`. Nothing else may set it (the field is not
     editable in the admin).
Until then the step looks mandatory but lets people carry on, because nobody could finish onboarding otherwise.
"""

AVAILABLE = False

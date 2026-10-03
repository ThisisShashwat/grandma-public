"""The starting wording for what a person ticks when they hand a project in, and the playable hosts Grandma does not accept.
Data only. Both are admin settings (program/runtime.py): these are the defaults until staff save something else."""

# Each is a thing the person declares. The key is what is stored; the text is what they read (keep a key stable once
# people have ticked it, the stored answers use it). Every box must be ticked, the server enforces it.
CHECKS = [
    {"key": "new_project", "text": "This is a brand new project. I started it after I talked to Grandma."},
    {"key": "no_old_project", "text": "I did not change an old project and call it new."},
    {"key": "not_elsewhere", "text": "I have never submitted this project to another program."},
    {"key": "ai_under_30", "text": "AI took less than 30% of my total time on this project."},
    {"key": "playable_works", "text": "My playable link works for anyone, and it is not on a host that falls asleep when nobody visits."},
    {"key": "repo_public", "text": "My repository is public."},
    {"key": "readme_runs", "text": "My README explains how to run it."},
    {"key": "screenshot_real", "text": "My screenshot shows the real project."},
    {"key": "time_real", "text": "The time I tracked is real."},
    {"key": "read_rules", "text": "I read Grandma's rules."},
]

# Free tiers that spin down when idle, and tunnels to somebody's own laptop: a reviewer opening the link must not meet a
# sleeping app. A host listed here also blocks every subdomain of it (streamlit.app blocks myapp.streamlit.app).
# From the maker's knowledge, not checked against each provider today: the owner edits the list in the admin.
BLOCKED_HOSTS = (
    "streamlit.app", "streamlit.io",       # Streamlit Community Cloud
    "onrender.com",                        # Render free web services
    "herokuapp.com",                       # Heroku dynos that sleep
    "hf.space",                            # Hugging Face free Spaces
    "koyeb.app",                           # Koyeb free instances
    "glitch.me",                           # Glitch
    "repl.co", "replit.dev",               # Replit's development hosts
    "gradio.live",                         # temporary Gradio share links
    "ngrok-free.app", "ngrok.io", "ngrok.app", "trycloudflare.com", "loca.lt", "serveo.net",   # tunnels to a laptop
)

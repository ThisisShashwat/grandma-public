"""The starting wording for what a person ticks when they hand a project in, and the playable hosts Grandma does not accept.
Data only. Both are admin settings (program/runtime.py): these are the defaults until staff save something else."""

# Each is a thing the person declares, most important first. The key is what is stored (keep a key stable once people have ticked it);
# the text is what they read; `applies_to` is "all", "software" or "hardware": the note shows the boxes for the project's kind and every
# box shown must be ticked, the server enforces it. Our own wording, adapted to Grandma (docs/submissions.md says where each came from).
CHECKS = [
    {"key": "follows_demands", "applies_to": "all", "text": "My project follows the demands Grandma gave me, and a reviewer can check every one of them."},
    {"key": "new_project", "applies_to": "all", "text": "I started this project after I talked to Grandma."},
    {"key": "no_old_project", "applies_to": "all", "text": "It is not an old project of mine with a new name. If I reused an old repository, I said why in my description."},
    {"key": "not_elsewhere", "applies_to": "all", "text": "These hours and this work have not been counted by any other program."},
    {"key": "own_work", "applies_to": "all", "text": "It is my own work, in my own time: not a copied tutorial, not someone else's code, not school work, not paid Hack Club work."},
    {"key": "works_as_described", "applies_to": "all", "text": "Everything my description says my project does is true and works."},
    {"key": "playable_works", "applies_to": "software",
     "text": "My link opens for anyone in a private window with no login (or I gave demo logins), on a host that stays awake, and a newcomer can try it in two minutes without compiling anything."},
    {"key": "demo_works", "applies_to": "hardware", "text": "The page I linked shows my project working (photos, a video or a viewer) and opens for anyone with no login."},
    {"key": "repo_public", "applies_to": "all", "text": "My repository is public and opens without signing in."},
    {"key": "readme_runs", "applies_to": "all", "text": "My README says what it is, how to set it up, and how to run, play or build it."},
    {"key": "commit_history", "applies_to": "all", "text": "My commits grew while I worked. It is not one giant upload at the end."},
    {"key": "bom_exact", "applies_to": "hardware", "text": "My parts list names every part exactly, including the ones I already own."},
    {"key": "schematic", "applies_to": "hardware", "text": "If it has electronics, I included a schematic or a wiring diagram."},
    {"key": "editable_cad", "applies_to": "hardware", "text": "Anything I print has editable CAD files (STEP or my own project files), not only an STL."},
    {"key": "build_new_hours", "applies_to": "hardware", "text": "If this is my build ship, I only claim the hours I worked since my design ship, and I said what changed."},
    {"key": "time_real", "applies_to": "all", "text": "The hours I claim are real work on this project: no idle timer, no scripts, nothing from other projects."},
    {"key": "ai_under_30", "applies_to": "all", "text": "AI took less than 30% of my total time, and I can explain every part of my project."},
    {"key": "screenshot_real", "applies_to": "all", "text": "My screenshot is a still picture of the real project, and any recording is on YouTube, Vimeo or a direct mp4, not Google Drive."},
    {"key": "art_share", "applies_to": "software", "text": "My art, models and sound took at most a quarter of my hours, unless they are the heart of the project."},
    {"key": "read_rules", "applies_to": "all", "text": "I read Grandma's rules, and I know a reviewer may reduce hours that look inflated."},
]

# Free tiers that spin down when idle, tunnels to somebody's own laptop, and notebooks that are not a project anyone can use: a reviewer
# opening the link must not meet a sleeping app. A host listed here also blocks every subdomain of it (streamlit.app blocks
# myapp.streamlit.app). From the maker's knowledge, not checked against each provider today: the owner edits the list in the admin.
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
    "colab.research.google.com", "mybinder.org",   # notebooks, not a project anyone can use
)

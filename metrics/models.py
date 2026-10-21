"""The two small tables behind the admin's Metrics page (docs/metrics.md). Neither holds an address, a browser, a page a person opened or anything
they typed: a signed in person's last visit per day, and a count of views per day for four public pages."""
from django.conf import settings
from django.db import models


class ActiveDay(models.Model):
    """One row per signed in person per day they used the site, with when they were last seen that day (written by metrics/activity.py)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    day = models.DateField(db_index=True)
    last_seen = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "day"], name="activeday_one_per_person_day")]
        verbose_name = "activity day"
        verbose_name_plural = "Metrics"

    def __str__(self):
        return f"{self.user_id} {self.day}"


class DayViews(models.Model):
    """How many times a public page was opened on a day, counted only while the COUNT_VISITS setting is on (written by metrics/visits.py). A number, never a visitor."""
    day = models.DateField()
    page = models.CharField(max_length=10)
    views = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "page"], name="dayviews_one_per_page_day")]
        verbose_name = "day of views"
        verbose_name_plural = "days of views"

    def __str__(self):
        return f"{self.day} {self.page} {self.views}"

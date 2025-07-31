from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'scrape-website-daily': {
        'task': 'authapp.scrap_task.crawl_website',
        'schedule': 86400.0,  # Daily (in seconds)
        # Alternatively use crontab: from celery.schedules import crontab
        # 'schedule': crontab(hour=3, minute=30)  # 3:30 AM daily
    },
}
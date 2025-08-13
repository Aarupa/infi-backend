# celery_config.py
import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

# Create the Celery app
app = Celery('myproject')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps
app.autodiscover_tasks()

# Configure periodic tasks
app.conf.beat_schedule = {
    'scrape-website-every-10-seconds': {
        'task': 'authapp.scrap_task.crawl_website',
        'schedule': 10.0,  # every 10 seconds
        'args': ('https://your-website.com', 2),  # 2 pages max
    },
}

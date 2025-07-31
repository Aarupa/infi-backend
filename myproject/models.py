from django.db import models
from django.utils import timezone

class ScrapedPage(models.Model):
    url = models.URLField(max_length=500, unique=True)
    base_url = models.URLField(max_length=500)
    title = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    is_priority = models.BooleanField(default=False)
    scraped_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-scraped_at']
        indexes = [
            models.Index(fields=['base_url']),
            models.Index(fields=['is_priority']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.url})"
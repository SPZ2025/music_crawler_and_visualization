from django.db import models

# Create your models here.
class Comment(models.Model):
    song_id = models.CharField(max_length= 64)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add= True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.song_id}:{self.content[:20]}"
    
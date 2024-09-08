from django.db import models


class User(models.Model):
    telegram_id = models.PositiveIntegerField()
    full_name = models.CharField(max_length=200, null=True)
    username = models.CharField(max_length=200, null=True)


class Package(models.Model):
    slug = models.CharField(max_length=200, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='packages')
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.URLField(max_length=200, null=True)
    last_check_version = models.CharField(max_length=200, null=True)

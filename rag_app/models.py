from django.db import models
from django.contrib.auth.models import User

class QueryHistory(models.Model):
    query = models.TextField()
    sql_query = models.TextField()
    response = models.TextField()
    data_fetched = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'query_history'
        
    def __str__(self):
        return f"Query: {self.query[:50]}..."

# Create your models here.

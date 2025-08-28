from django.urls import path
from .views import OfflineRAGView, SchemaInfoView, QueryHistoryView

urlpatterns = [
    path('query/', OfflineRAGView.as_view(), name='rag_query'),
    path('schema/', SchemaInfoView.as_view(), name='schema_info'),
    path('history/', QueryHistoryView.as_view(), name='query_history'),
]


from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',                    views.dashboard_view,      name='dashboard'),
    path('predict/',                      views.predict_view,        name='predict'),
    path('records/',                      views.records_view,        name='records'),
    path('records/<int:report_id>/',      views.report_detail_view,  name='report_detail'),
    path('records/<int:report_id>/pdf/',  views.download_report_pdf, name='download_report'),
    path('history/',                      views.history_view,        name='history'),
]

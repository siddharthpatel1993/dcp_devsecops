from django.urls import path
from . import views 

urlpatterns=[
        path("",views.index,name="index"),
        path("input",views.inputfile,name="input"),
        path("result1",views.result1,name="result1"),
        path("result2",views.result2,name="result2"),
        path("chatbot/", views.chatbot, name='chatbot'),
        path("notes/", views.notes, name='notes'),
        ]

from django import forms
from django.forms import ModelForm, Textarea
from .models import *


class TaskForm(ModelForm):
    class Meta:
        model = Task
        fields = ['assignee', 'title', 'description', 'due', 'priority', 'difficulty']
        widgets = {
            'due': forms.DateInput(attrs={'class': 'datepicker'}),
        }

    def __init__(self, team, *args, **kwargs):
        super(TaskForm, self).__init__(*args, **kwargs)
        self.fields['assignee'].queryset = team.developer_set.all()


class CommentForm(ModelForm):
    class Meta:
        model = Comment
        fields = ['body', 'file_url']
        widgets = {
            'body': Textarea(attrs={'cols': 20, 'rows': 3}),
        }

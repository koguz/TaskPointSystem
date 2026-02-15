from django.db.models.base import Model
from django.forms import ModelForm, DateInput, Textarea
from django.core.exceptions import ValidationError
from django import forms

from .models import *

class MasterCourseForm(ModelForm):
    class Meta:
        model = MasterCourse
        fields = ['code', 'name']

class CourseForm(ModelForm):
    class Meta:
        model = Course
        fields = ['academic_year', 'semester', 'group_weight', 'individual_weight']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        academic_year_choices = Course.get_academic_year_choices()
        self.fields['academic_year'].widget = forms.Select(choices=academic_year_choices)
        self.fields['academic_year'].initial = Course.get_default_academic_year()

class MilestoneForm(ModelForm):
    class Meta:
        model = Milestone
        fields = ['name', 'description', 'weight', 'due']
        widgets = {
            'due': DateInput(attrs={'class': 'datepicker'}),
        }

class TaskForm(ModelForm):
    class Meta:
        model = Task 
        fields = ['title', 'description', 'priority', 'promised_date']
        widgets = {
            'promised_date': DateInput(attrs={'class': 'datepicker'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        due = cleaned_data.get('promised_date')
        from datetime import date 
        if due < date.today():
            raise ValidationError("Promised date is in the past!")
        

class CommentForm(ModelForm):
    class Meta:
        model=Comment 
        fields = ['body', 'file_url']
        widgets = {
            'body': Textarea(attrs={'cols': 20, 'rows': 5}),
        }

class TeamFormStd(ModelForm):
    class Meta:
        model = Team 
        fields = ['name', 'github']

class EmailChangeForm(ModelForm):
    class Meta:
        model = User
        fields = ['email']

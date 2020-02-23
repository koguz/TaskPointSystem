import datetime

from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Course, Milestone, Team, Task, Developer, Comment, Supervisor, past_date_validator

# Create your tests here.


class TaskModelTests(TestCase):
    def test_past_date_validator_past(self):
        past_date = timezone.now() - datetime.timedelta(days=1)
        past_date = past_date.date()
        task = Task(due=past_date)
        self.assertRaises(ValidationError)

    def test_past_date_validator_not_past(self):
        past_date = timezone.now() + datetime.timedelta(days=1)
        past_date = past_date.date()
        task = Task(due=past_date)
        self.assertEqual(past_date_validator(task.due), None)

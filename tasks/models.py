import datetime

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User


def past_date_validator(value):
    if datetime.date.today() >= value:
        raise ValidationError(
            _('%(value)s is in the past!'),
            params={'value': value},
        )

# in class definitions, foreign keys and relations should come first


class Course(models.Model):
    name = models.CharField("Course Name", max_length=256)
    number_of_students = models.PositiveSmallIntegerField("Number of Students", default=40, validators=[MaxValueValidator(99), MinValueValidator(1)])
    team_weight = models.PositiveSmallIntegerField(
        "Team weight",
        default=40,
        validators=[MaxValueValidator(99), MinValueValidator(1)]
    )
    ind_weight = models.PositiveSmallIntegerField(
        "Individual weight",
        default=60,
        validators=[MaxValueValidator(99), MinValueValidator(1)]
    )

    def __str__(self):
        return self.name

    def get_number_0f_students(self):
        return self.number_of_students

    def get_current_milestone(self):
        return self.milestone_set.all().order_by('due').exclude(due__lte=datetime.date.today())[0]


class Milestone(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    name = models.CharField("Milestone", max_length=128)
    description = models.TextField("Milestone details")
    weight = models.PositiveSmallIntegerField(
        "Weight",
        default=10,
        validators=[MaxValueValidator(100), MinValueValidator(1)]
    )
    due = models.DateField("Due Date")

    def __str__(self):
        return self.name


class Supervisor(models.Model):
    id = models.CharField("ID", max_length=12, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.get_name()

    def get_name(self):
        return self.user.first_name + " " + self.user.last_name


class Team(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    name = models.CharField("Team Name", max_length=128)
    github = models.CharField("Git Page", max_length=256, null=True)
    supervisor = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, blank=True, null=True)
    team_size = models.PositiveSmallIntegerField("Team size", default=4, validators=[MaxValueValidator(99), MinValueValidator(1)])

    def __str__(self):
        return self.name

    # since tasks belong to milestones, we have to compute grade for
    # every milestone...
    def get_all_task_points(self, m):
        p = 0
        for task in self.task_set.all().filter(milestone=m):
            p = p + task.get_points()
        return p

    def get_all_accepted_points(self, m):
        p = 0
        for task in self.task_set.all().filter(milestone=m):
            if task.status == 5:
                p = p + task.get_points()
        return p

    def get_milestone_list(self):
        milestone_list = {}
        for m in self.course.milestone_set.all():
            milestone_list[m.name] = self.get_team_grade(m)
        return milestone_list

    # this should be based on milestone, as well.
    def get_team_grade(self, m):
        g = 0
        if self.get_all_task_points(m) > 0:
            g = round((self.get_all_accepted_points(m) / self.get_all_task_points(m)) * 100)
        return g

    def get_developer_average(self, m):
        return self.get_all_task_points(m) / self.developer_set.count()

    def get_team_size(self):
        size = self.team_size
        return size


class Developer(models.Model):
    id = models.CharField("ID", max_length=12, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.get_name()

    def get_name(self):
        return self.user.first_name + " " + self.user.last_name

    def get_all_accepted_points(self, m):
        p = 0
        for task in self.assignee.all().filter(milestone=m):
            if task.status == 5:
                p = p + task.get_points()
        return p

    # since we compute the team grade with the milestone, we should compute
    # the individual grade as such, too...
    def get_developer_grade(self, m):
        g = 0
        if self.team.get_developer_average(m) > 0:
            g = round((self.get_all_accepted_points(m) / self.team.get_developer_average(m)) * 100)
            if g > 100:
                g = 100
        return g

    # this function is for the "view all teams" - we have to get the milestone names and points
    # for those milestones in a dictionary, so that i can loop through it in the template...
    def get_milestone_list(self):
        milestone_list = {}
        for m in self.team.course.milestone_set.all():
            milestone_list[m.name] = self.get_developer_grade(m)
        return milestone_list

    def get_project_grade(self):
        # loop through the milestones, get developer grade and team grade...
        team_grade = 0
        ind_grade = 0
        c = self.team.course
        for m in c.milestone_set.all():
            team_grade = team_grade + self.team.get_team_grade(m) * (m.weight / 100)
            ind_grade = ind_grade + self.get_developer_grade(m) * (m.weight / 100)
        return round(team_grade * (c.team_weight / 100) + ind_grade * (c.ind_weight / 100))


class Task(models.Model):
    PRIORITY = (
        (3, 'Urgent'),
        (2, 'Planned'),
        (1, 'Low'),
    )
    DIFFICULTY = (
        (3, 'Difficult'),
        (2, 'Normal'),
        (1, 'Easy'),
    )
    STATUS = (
        (1, "Review"),
        (2, "Working on it"),
        (3, "Waiting for review"),
        (4, "Waiting for supervisor grade"),
        (5, "Rejected"),
        (6, "Accepted"),
    )
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE)
    creator = models.ForeignKey(User, related_name='creator', on_delete=models.SET_NULL, blank=True, null=True)
    assignee = models.ForeignKey(
        Developer,
        on_delete=models.CASCADE,
        related_name='assignee',
        verbose_name="Assigned to"
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    title = models.CharField("Brief task name", max_length=256)
    description = models.TextField("Description")
    due = models.DateField("Due Date", validators=[past_date_validator])
    date = models.DateTimeField("Created on", auto_now_add=True)
    completed = models.DateTimeField("Completed on", auto_now=True, blank=True, null=True)
    priority = models.PositiveSmallIntegerField("Priority", choices=PRIORITY, default=2)
    difficulty = models.PositiveSmallIntegerField("Difficulty", choices=DIFFICULTY, default=2)
    modifier = models.PositiveSmallIntegerField(
        "Modifier",
        default=3,
        validators=[MaxValueValidator(5), MinValueValidator(1)]
    )
    status = models.PositiveSmallIntegerField("Status", choices=STATUS, default=1)
    valid = models.BooleanField("Is Valid", default=False)

    def get_points(self):
        return (self.difficulty*self.priority)+self.modifier

    def already_voted(self, developer):
        if Vote.objects.filter(task=self, voter=developer):
            return True
        return False

    def get_creation_accept_votes(self):

        if Vote.objects.filter(task=self, vote_type=1).count() >= self.team.get_team_size()*0.50:
            self.status = 2
            self.save()

        return Vote.objects.filter(task=self, vote_type=1)

    def get_creation_reject_votes(self):
        return Vote.objects.filter(task=self, vote_type=2)

    def __str__(self):
        return self.team.__str__() + ": " + self.title + " " + self.description[0:15]


class Comment(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    body = models.TextField("Comment")
    file_url = models.URLField("File URL", max_length=512, blank=True, null=True)
    date = models.DateTimeField("Date", auto_now_add=True)

    def __str__(self):
        return self.body


class Vote(models.Model):
    VOTE_TYPE = (
        (1, 'Task Creation Accepted'),
        (2, 'Task Creation Rejected'),
        (3, 'Task Submission Accepted'),
        (4, 'Task Submission Rejected'),
    )

    voter = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    task = models.ForeignKey(Task, on_delete=models.DO_NOTHING)
    vote_type = models.PositiveSmallIntegerField("Vote Type", choices=VOTE_TYPE, default=1)
    date = models.DateTimeField("Date", auto_now_add=True)

    def __str__(self):
        return self.voter.__str__() + " voted for " + self.task.title

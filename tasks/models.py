import datetime
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from anytree import Node


def past_date_validator(value):
    if datetime.date.today() >= value:
        raise ValidationError(
            _('%(value)s is in the past!'),
            params={'value': value},
        )

# in class definitions, foreign keys and relations should come first


class Course(models.Model):
    name = models.CharField("Course Name", max_length=256)
    number_of_students = models.PositiveSmallIntegerField(
        "Number of Students",
        default=40,
        validators=[MaxValueValidator(99), MinValueValidator(1)]
    )
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

    def get_number_of_students(self):
        return self.number_of_students

    def get_current_milestone(self):
        milestones = self.milestone_set.all().order_by('due').exclude(due__lte=datetime.date.today())

        if len(milestones) > 0:
            return milestones[0]

        return "No Milestone"


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
    # will we show these in teams.html
    name = models.CharField("Team Name", max_length=128)
    name_change_count = models.PositiveSmallIntegerField(
        "Name Change Count",
        default=0,
        validators=[MaxValueValidator(3), MinValueValidator(0)]
    )
    github = models.CharField("Git Page", max_length=256, null=True)
    supervisor = models.ForeignKey(Supervisor, on_delete=models.SET_NULL, blank=True, null=True)
    team_size = models.PositiveSmallIntegerField(
        "Team size",
        default=4,
        validators=[MaxValueValidator(99), MinValueValidator(1)]
    )

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
        return self.get_all_task_points(m) / self.get_team_members().count()

    def get_team_size(self):
        size = self.team_size
        return size

    def get_team_members(self):
        return Developer.objects.all().filter(developerteam__team_id=self.id)

    def get_tasks(self):
        return self.task_set.all()


class Developer(models.Model):
    id = models.CharField("ID", max_length=12, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.get_name()

    def get_name(self):
        return self.user.first_name + " " + self.user.last_name

    def get_only_name(self):
        return self.user.first_name

    def get_all_accepted_points(self, m):
        p = 0
        for task in self.assignee.all().filter(milestone=m):
            if task.status == 5:
                p = p + task.get_points()
        return p

    # since we compute the team grade with the milestone, we should compute
    # the individual grade as such, too...
    def get_developer_grade(self, team, milestone):
        g = 0
        if team.get_developer_average(milestone) > 0:
            g = round((self.get_all_accepted_points(milestone) / team.get_developer_average(milestone)) * 100)
            if g > 100:
                g = 100
        return g

    # this function is for the "view all teams" - we have to get the milestone names and points
    # for those milestones in a dictionary, so that i can loop through it in the template...
    def get_milestone_list(self, team):
        milestone_list = {}
        for milestone in team.course.milestone_set.all():
            milestone_list[milestone.name] = self.get_developer_grade(team, milestone)
        return milestone_list

    def get_project_grade(self, team):
        # loop through the milestones, get developer grade and team grade...
        team_grade = 0
        ind_grade = 0
        c = team.course
        for milestone in c.milestone_set.all():
            team_grade = team_grade + team.get_team_grade(milestone) * (milestone.weight / 100)
            ind_grade = ind_grade + self.get_developer_grade(team, milestone) * (milestone.weight / 100)
        return round(team_grade * (c.team_weight / 100) + ind_grade * (c.ind_weight / 100))

    def get_teams(self):
        return Team.objects.all().filter(developerteam__developer=self)

    def is_in_team(self, team):
        if DeveloperTeam.objects.all().filter(developer_id=self.id, team_id=team.id):
            return True
        return False


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
        return (self.difficulty * self.priority) + self.modifier

    def already_voted_for_creation(self, developer):
        if Vote.objects.filter(task=self, voter=developer, vote_type__range=(1, 2)):
            return True
        return False

    def already_voted_for_submission(self, developer):
        if Vote.objects.filter(task=self, voter=developer, vote_type__range=(3, 4)):
            return True
        return False

    def get_creation_accept_votes(self):
        return Vote.objects.filter(task=self, vote_type=1)

    def get_creation_change_votes(self):
        return Vote.objects.filter(task=self, vote_type=2)

    def get_submission_accept_votes(self):
        return Vote.objects.filter(task=self, vote_type=3)

    def get_submission_change_votes(self):
        return Vote.objects.filter(task=self, vote_type=4)

    def apply_self_accept(self, task_assignee, vote_type):
        vote = Vote(voter=task_assignee.user, task=self)
        vote.vote_type = vote_type
        vote.save()

    def check_for_status_change(self):
        if (
                Vote.objects.filter(task=self, vote_type=1).count() > self.team.get_team_size() * 0.50 and
                self.status == 1
        ):
            self.status = 2
            self.save()

        elif (
                Vote.objects.filter(task=self, vote_type=3).count() > self.team.get_team_size() * 0.50 and
                self.status == 3
        ):
            self.status = 4
            self.save()

        elif (
                Vote.objects.filter(task=self, vote_type=4).count() >= self.team.get_team_size() * 0.50 and
                self.status == 3
        ):
            # resetting request change votes for submission so that when submitted again team members can vote
            Vote.objects.filter(task=self, vote_type__range=(3, 4)).delete()
            self.status = 2
            self.save()

    def get_final_answer(self):
        return Comment.objects.get(task=self, is_final=1)

    def get_differences_from(self, task):
        differences = {
            "assignee": "",
            "title": "",
            "description": "",
            "due_date": "",
            "priority": "",
            "difficulty": "",
        }

        different_attributes = filter(lambda field: getattr(self, field, None) != getattr(task, field, None), differences.keys())

        for attribute in different_attributes:
            differences[attribute] = self.__getattribute__(attribute)

        print(differences)
        return differences

    def is_different_from(self, task):
        differences = self.get_differences_from(task)
        for value in differences.values():
            if value != "":
                return True

        return False

    def __str__(self):
        return self.team.__str__() + ": " + self.title + " " + self.description[0:15]


class Comment(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    response_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True)
    body = models.TextField("Comment")
    file_url = models.URLField("File URL", max_length=512, blank=True, null=True)
    date = models.DateTimeField("Date", auto_now_add=True)
    points = models.IntegerField("Upvotes", default=0)
    is_final = models.BooleanField(default=False)

    def is_direct_comment(self):
        if self.response_to:
            return False
        return True

    # https://anytree.readthedocs.io/en/2.8.0/index.html, https://pypi.org/project/anytree/
    def make_children_nodes(self, depth, parent):
        children = Comment.objects.filter(response_to=self)
        if parent:
            root = Node(parent=parent, id=self.id, depth=depth)
        else:
            root = Node(id=self.id, depth=depth)
        for child in children:
            self.make_children_nodes(child, depth + 1, root)

    def __str__(self):
        return self.body


class Vote(models.Model):
    VOTE_TYPE = (
        (1, 'Creation Accepted'),
        (2, 'Creation Change Requested'),
        (3, 'Submission Accepted'),
        (4, 'Submission Change Requested'),
    )

    # VOTES WILL BE DELETED IF EITHER THE VOTER OR THE TASK IS DELETED !
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    vote_type = models.PositiveSmallIntegerField("Vote Type", choices=VOTE_TYPE, default=1)
    date = models.DateTimeField("Date", auto_now_add=True)

    # should we add is active for votes?
    # is_active = models.BooleanField("Is Active", default=True)

    def __str__(self):
        return self.voter.__str__() + " voted for " + self.task.title


class DeveloperTeam(models.Model):
    developer = models.ForeignKey(Developer, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    def __str__(self):
        return self.developer.get_name() + " is in team " + self.team.name

    class Meta:
        unique_together = ['developer', 'team']


class ActionRecord(models.Model):
    ACTION_TYPE = (
        (1, 'Task Create'),
        (2, 'Task Edit'),
        (3, 'Task Submit'),
        (4, 'Task Comment'),
        (5, 'Task Final Comment'),
        (6, 'Task Creation Accept'),
        (7, 'Task Creation No Vote'),
        (8, 'Task Creation Request Change'),
        (9, 'Task Submission Accept'),
        (10, 'Task Submission No Vote'),
        (11, 'Task Submission Request Change'),
        (12, 'Task Reject'),
    )
    action_type = models.PositiveSmallIntegerField("Vote Type", choices=ACTION_TYPE, default=0)
    actor = models.ForeignKey(User, on_delete=models.RESTRICT)
    object = models.ForeignKey(Task, on_delete=models.RESTRICT)
    action_description = models.CharField("Action Description", max_length=256)
    # TODO: make datetime turkey time
    action_datetime = models.DateTimeField("Created on", auto_now=True)

    @staticmethod
    def task_create(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' CREATED a new task called: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor.user,
            object=object,
            action_description=action_description,
        )
        action_record.save()
        return action_record

    @staticmethod
    def task_edit(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' EDITED the task: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor.user,
            object=object,
            action_description=action_description,
        )
        action_record.save()
        return action_record

    @staticmethod
    def task_submit(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' SUBMITTED the task: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor.user,
            object=object,
            action_description=action_description,
        )
        action_record.save()

    @staticmethod
    def task_comment(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' COMMENTED on the task: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor,
            object=object,
            action_description=action_description,
        )
        action_record.save()

    @staticmethod
    def task_comment_final(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' FINAL COMMENTED on the task: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor,
            object=object,
            action_description=action_description,
        )
        action_record.save()

    @staticmethod
    def task_vote(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' VOTED for the task: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor,
            object=object,
            action_description=action_description,
        )
        action_record.save()

    @staticmethod
    def task_approval(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' ACTED on the task: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor,
            object=object,
            action_description=action_description,
        )
        action_record.save()


class TaskDifference(models.Model):
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
    action_record = models.ForeignKey(ActionRecord, on_delete=models.RESTRICT)
    task = models.ForeignKey(Task, on_delete=models.RESTRICT)
    assignee = models.ForeignKey(Developer, on_delete=models.RESTRICT)
    title = models.CharField("Brief task name", max_length=256)
    description = models.TextField("Description")
    priority = models.PositiveSmallIntegerField("Priority", choices=PRIORITY)
    difficulty = models.PositiveSmallIntegerField("Difficulty", choices=DIFFICULTY)
    datetime = models.DateTimeField("Created on", auto_now=True)

    @staticmethod
    def record_task_difference(task, action_record):
        task_difference = TaskDifference(
            action_record=action_record,
            task=task,
            assignee=task.assignee,
            title=task.title,
            description=task.description,
            priority=task.priority,
            difficulty=task.difficulty,
        )
        task_difference.save()

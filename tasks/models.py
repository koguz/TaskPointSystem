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

    def is_in_team(self, user):
        developer = Developer.objects.filter(user=user).first()
        supervisor = Supervisor.objects.filter(user=user).first()

        if developer:
            return DeveloperTeam.objects.all().filter(developer=developer, team=self).count() > 0
        elif supervisor:
            return Team.objects.filter(supervisor=supervisor, pk=self.id).count() > 0


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
    created_on = models.DateTimeField("Created on", auto_now_add=True)
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
        if Vote.objects.filter(task=self, vote_type=self.status).count() >= self.team.get_team_size():
            self.status = self.status + 1
            self.save()
        elif (
            Vote.objects.filter(task=self, vote_type=4).count() >= self.team.get_team_size() - 1 and
            self.status == 3
        ):
            self.unflag_final_comment()

    def unflag_final_comment(self):
        final_comment = Comment.objects.get(task=self, is_final=True)
        final_comment.is_final = False
        final_comment.save()
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

        return differences

    def is_different_from(self, task):
        differences = self.get_differences_from(task)
        for value in differences.values():
            if value != "":
                return True

        return False

    def can_be_changed_status_by(self, user):
        developer = Developer.objects.filter(user=user).first()
        supervisor = Supervisor.objects.filter(user=user).first()

        if developer == self.assignee and self.team.is_in_team(user):
            return True
        elif supervisor and self.team.is_in_team(user):
            return True

        return False

    def can_be_voted_by(self, user):
        if user is None or Supervisor.objects.filter(user=user).first():
            return False

        developer = Developer.objects.filter(user=user).first()
        # self.status and vote_types are coincidentally matches thus only task's status is used for checking
        developer_not_voted_before = Vote.objects.all().filter(
            task=self,
            vote_type__range=(self.status, self.status + 1),
            voter__developer=developer,
        ).count() < 1
        developer_is_in_tasks_team = self.team.is_in_team(user)

        if developer_is_in_tasks_team and developer_not_voted_before:
            return True

        return False

    def half_the_team_accepted(self):
        team_size = Team.objects.get(pk=self.team.id).team_size
        return Vote.objects.all().filter(
            task=self,
            vote_type=self.status,
        ).count() >= team_size * 0.50

    def get_history(self):
        task_difference_elements = TaskDifference.objects.filter(task=self).order_by('-created_on').values()
        task_difference_elements_length = len(task_difference_elements)
        task_history = []

        task_creation_history_element = task_difference_elements[task_difference_elements_length - 1]
        assignee_id = task_creation_history_element.pop('assignee_id', None)
        task_creation_history_element['assignee'] = Developer.objects.get(pk=assignee_id)
        task_creation_history_element.pop('action_record_id', None)
        task_creation_history_element.pop('task_id', None)
        task_creation_history_element.pop('id', None)
        task_history.append(task_creation_history_element)

        # TaskDifference entries
        for index in reversed(range(0, task_difference_elements_length - 1)):
            task_one_dict = task_difference_elements[index]
            task_two_dict = task_difference_elements[index + 1]
            assignee_id = task_one_dict.pop('assignee_id', None)
            task_one_dict['assignee'] = Developer.objects.get(pk=assignee_id)
            task_one_dict.pop('action_record_id', None)
            task_one_dict.pop('task_id', None)
            task_one_dict.pop('id', None)

            task_one_set = set(task_one_dict.items())
            task_two_set = set(task_two_dict.items())
            task_difference = task_one_set - task_two_set
            task_history.append(dict(task_difference))

        task_actions = ActionRecord.objects.filter(object=self).order_by('-created_on').values()
        action_types = dict(ActionRecord.ACTION_TYPE)

        for task_action in task_actions:
            action_owner = Developer.objects.filter(user_id=task_action['actor_id']).first()

            if action_owner is None:
                action_owner = Supervisor.objects.filter(user_id=task_action['actor_id']).first()

            action_desc = action_owner.get_name() + ' performed ' + action_types.get(task_action['action_type'])
            task_history.append({
                'action_description': action_desc,
                'created_on': task_action['created_on'],
            })

        task_history_sorted = sorted(task_history, key=lambda i: i['created_on'])
        task_history_sorted.reverse()

        return task_history_sorted

    def __str__(self):
        return self.team.__str__() + ": " + self.title + " " + self.description[0:15]


class Comment(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    response_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True)
    body = models.TextField("Comment")
    file_url = models.URLField("File URL", max_length=512, blank=True, null=True)
    created_on = models.DateTimeField("Date", auto_now_add=True)
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
    created_on = models.DateTimeField("Date", auto_now_add=True)

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
        (7, 'Task Status Change To Working On It'),
        (8, 'Task Creation Request Change'),
        (9, 'Task Submission Accept'),
        (10, 'Task Status Change To Waiting For Review'),
        (11, 'Task Submission Request Change'),
        (12, 'Task Reject'),
    )
    action_type = models.PositiveSmallIntegerField("Vote Type", choices=ACTION_TYPE, default=0)
    actor = models.ForeignKey(User, on_delete=models.RESTRICT)
    object = models.ForeignKey(Task, on_delete=models.RESTRICT)
    action_description = models.CharField("Action Description", max_length=256)
    # TODO: make datetime turkey time
    created_on = models.DateTimeField("Created on", auto_now=True)

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
        return action_record

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
        return action_record

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
        return action_record

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
        return action_record

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
        return action_record

    @staticmethod
    def task_status_change_by_developer(action_type, actor, object):
        action_description = "'" + actor.__str__() + "' CHANGED THE STATUS of the task: '" + object.title + "'"
        action_record = ActionRecord(
            action_type=action_type,
            actor=actor.user,
            object=object,
            action_description=action_description,
        )
        action_record.save()
        return action_record


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
    due = models.DateField("Due Date")
    priority = models.PositiveSmallIntegerField("Priority", choices=PRIORITY)
    difficulty = models.PositiveSmallIntegerField("Difficulty", choices=DIFFICULTY)
    created_on = models.DateTimeField("Created on", auto_now=True)

    @staticmethod
    def record_task_difference(task, action_record):
        task_difference = TaskDifference(
            action_record=action_record,
            task=task,
            assignee=task.assignee,
            title=task.title,
            description=task.description,
            due=task.due,
            priority=task.priority,
            difficulty=task.difficulty,
        )
        task_difference.save()

class Notification(models.Model):
    user = models.ForeignKey(User, related_name='user', on_delete=models.SET_NULL, null=True)
    body = models.CharField("Notification Body", max_length=256)
    related_task = models.ForeignKey(Task, related_name='user', on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField("Sent on", auto_now=True)
    is_seen = models.BooleanField("Seen", default=False)
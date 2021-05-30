import datetime
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
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
    TERM = (
        (2, 'Spring'),
        (1, 'Winter'),
    )
    name = models.CharField("Course Name", max_length=256)
    course = models.CharField("Course", max_length=256)
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
    section = models.PositiveSmallIntegerField("Section", default=1, blank=False, validators=[MaxValueValidator(99), MinValueValidator(1)])
    year = models.PositiveSmallIntegerField("Year", default=2020, blank=False)
    term = models.PositiveSmallIntegerField("Term", choices=TERM, default=1, blank=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['course', 'section', 'year', 'term', 'section'], name='Course unique constraint')
        ]

    def __str__(self):
        return self.course + "-" + "Section " + str(self.section)

    def get_number_of_students(self):
        return self.number_of_students

    def get_current_milestone(self):
        milestones = self.milestone_set.all().order_by('due').exclude(due__lte=datetime.date.today())

        if len(milestones) > 0:
            return milestones[0]

        return "No Milestone"

    def create_course_name(self):
        self.name = str(self.course) + "-" + str(self.year) + "-" + str(self.term) + "-" + str(self.section)
        self.save()


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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['course', 'name'], name='Milestone course constraint')
        ]

    def __str__(self):
        return self.name


class Supervisor(models.Model):
    id = models.CharField("ID", max_length=12, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    photo_url = models.CharField("Photo URL:", null=True, blank=True, max_length=2038)

    def __str__(self):
        return self.get_name()

    def get_name(self):
        return self.user.first_name + " " + self.user.last_name

    def calculate_point_pool(self, course_id):
        developer_team = []
        supervised_teams = Team.objects.all().filter(supervisor=self.id, course_id=course_id)
        for team in supervised_teams:
            developer_team.append(team.get_team_members())
        for team in developer_team:
            for developer in team:

                PointPool.get_all_tasks(course_id, developer)
                PointPool.get_all_votes(course_id, developer)

        return PointPool.scale_point_pool_grades(course_id)


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

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['course', 'name'], name='Course team name constraint')
        ]

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
            if task.status == 6:
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
        return self.team_size

    def get_team_members(self):
        return Developer.objects.filter(developerteam__team_id=self.id)

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
    photo_url = models.CharField("Photo URL:", null=True, blank=True, max_length=2038)
    # team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return self.get_name()

    def get_name(self):
        return self.user.first_name + " " + self.user.last_name

    def get_only_name(self):
        return self.user.first_name

    def get_all_accepted_points(self, team, milestone):
        p = 0

        for task in self.assignee.all().filter(milestone=milestone, team=team):
            if task.status == 6:
                p = p + task.get_points()

        return p

    # since we compute the team grade with the milestone, we should compute
    # the individual grade as such, too...
    def get_developer_grade(self, team, milestone):
        g = 0

        if team.get_developer_average(milestone) > 0:
            g = round((self.get_all_accepted_points(team, milestone) / team.get_developer_average(milestone)) * 100)

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
        individual_grade = 0
        team_course = team.course

        for milestone in team_course.milestone_set.all():
            team_grade = team_grade + team.get_team_grade(milestone) * (milestone.weight / 100)
            individual_grade = individual_grade + self.get_developer_grade(team, milestone) * (milestone.weight / 100)

        return round(team_grade * (team_course.team_weight / 100) + individual_grade * (team_course.ind_weight / 100))

    def get_teams(self):
        return Team.objects.all().filter(developerteam__developer=self)

    def get_all_tasks(self):
        return Task.objects.filter(assignee=self)

    def get_active_tasks(self):
        return Task.objects.filter(assignee=self, status__range=(1, 3))

    def get_attention_needed_tasks(self):
        return Task.objects.filter(team__developerteam__developer=self, status__in=(1, 3)).exclude(assignee=self)


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
    title = models.CharField("Task title", max_length=50)
    description = models.TextField("Description", max_length=256)
    due = models.DateField("Due Date", validators=[past_date_validator])
    created_on = models.DateTimeField("Created on", auto_now_add=True, null=False)
    creation_approved_on = models.DateTimeField("Creation approved on", blank=True, null=True)
    submission_approved_on = models.DateTimeField("Submission approved on", blank=True, null=True)
    completed_on = models.DateTimeField("Completed on", blank=True, null=True)
    last_modified = models.DateTimeField("Last Modified", auto_now=True)
    priority = models.PositiveSmallIntegerField("Priority", choices=PRIORITY, default=2)
    difficulty = models.PositiveSmallIntegerField("Difficulty", choices=DIFFICULTY, default=2)
    modifier = models.PositiveSmallIntegerField(
        "Modifier",
        default=3,
        validators=[MaxValueValidator(5), MinValueValidator(1)]
    )
    status = models.PositiveSmallIntegerField("Status", choices=STATUS, default=1)

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
        vote = Vote(voter=task_assignee, task=self)
        vote.vote_type = vote_type
        vote.save()

    def check_for_status_change(self):
        if Vote.objects.filter(task=self, vote_type=self.status).count() >= self.team.get_team_size():
            self.status = self.status + 1
            if self.status == 4:
                self.submission_approved_on = datetime.datetime.now()
            elif self.status == 2:
                self.creation_approved_on = datetime.datetime.now()
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

        different_attributes = filter(lambda field: getattr(self, field, None) != getattr(task, field, None),
                                      differences.keys())

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
            voter=developer,
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

        if task_difference_elements_length > 0:
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
    body = models.TextField("Comment")
    file_url = models.URLField("File URL", max_length=512, blank=True, null=True)
    created_on = models.DateTimeField("Date", auto_now_add=True)
    points = models.IntegerField("Upvotes", default=0)
    is_final = models.BooleanField(default=False)

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
    voter = models.ForeignKey(Developer, on_delete=models.CASCADE)
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
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    object = models.ForeignKey(Task, on_delete=models.CASCADE)
    action_description = models.CharField("Action Description", max_length=256)
    # TODO: make datetime turkey time
    created_on = models.DateTimeField("Created on", auto_now_add=True)

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
    action_record = models.ForeignKey(ActionRecord, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    assignee = models.ForeignKey(Developer, on_delete=models.CASCADE)
    title = models.CharField("Brief task name", max_length=256)
    description = models.TextField("Description")
    due = models.DateField("Due Date")
    priority = models.PositiveSmallIntegerField("Priority", choices=PRIORITY)
    difficulty = models.PositiveSmallIntegerField("Difficulty", choices=DIFFICULTY)
    created_on = models.DateTimeField("Created on", auto_now_add=True)

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
    timestamp = models.DateTimeField("Sent on", auto_now_add=True)
    is_seen = models.BooleanField("Seen", default=False)


class PointPool(models.Model):
    developer = models.ForeignKey(Developer, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, default=1, on_delete=models.CASCADE)
    point = models.PositiveIntegerField(default=0)

    @staticmethod
    def get_all_tasks(course_id, developer):
        try:
            point_pool_entry = PointPool.objects.get(developer=developer, course__id=course_id)
        except PointPool.DoesNotExist:
            point_pool_entry = PointPool(developer=developer, course_id=course_id)
            point_pool_entry.save()

        all_accepted_tasks_list = Task.objects.select_related('team__course').filter(assignee=developer,
                                                                                     status=6)  # All tasks that are accpeted
        all_rejected_tasks_list = Task.objects.select_related('team__course').filter(assignee=developer,
                                                                                     status=5)  # All tasks that are rejected
        for task in all_accepted_tasks_list:
            entry = GraphIntervals.objects.filter(difficulty=task.difficulty, priority=task.priority).first()

            if entry is None:
                entry = GraphIntervals(course_id=course_id, difficulty=task.difficulty, priority=task.priority)
                entry.save()

            submission_duration = ((task.completed_on.date() - task.created_on.date()).total_seconds() / 3600)
            lower_bound = entry.lower_bound
            upper_bound = entry.upper_bound

            if lower_bound == -1 and upper_bound == -1:  # No special point pool interval given.
                point_pool_entry.point += 1
            elif lower_bound < submission_duration < upper_bound:  # An interval is given for that priority-difficulty task.
                point_pool_entry.point += 1

        point_pool_entry.point -= len(all_rejected_tasks_list)

        point_pool_entry.save()

    @staticmethod
    def get_all_votes(course_id, developer):
        point_pool_entry = PointPool.objects.get(course_id=course_id, developer_id=developer.id)

        all_votes_list = Vote.objects.filter(task__team__course=course_id, voter=developer)  # All votes that are voted.
        for vote in all_votes_list:
            task = Task.objects.get(id=vote.task_id)
            if task.status == 5 and (
                    vote.vote_type == 1 or vote.vote_type == 3):  # If a rejected task is voted as accept decrease points by 4.
                point_pool_entry.point -= 1
            elif task.status == 6 and (vote.vote_type == 1 or vote.vote_type == 3):
                point_pool_entry.point += 1

        point_pool_entry.save()

    @staticmethod
    def scale_point_pool_grades(course_id):
        points_and_developers = {}
        point_pool_of_course = PointPool.objects.values('point', 'developer__user__first_name', 'developer__user__last_name').filter(course_id=course_id).order_by('-point')
        highest_grade = point_pool_of_course[0]['point']
        for point_pool in point_pool_of_course:
            if point_pool['point'] == point_pool_of_course[0]['point']:
                points_and_developers.update({point_pool['developer__user__first_name'] + point_pool['developer__user__last_name']: 100})
            else:
                scaled_grade = (point_pool['point'] * 100)/highest_grade
                points_and_developers.update({point_pool['developer__user__first_name'] + point_pool['developer__user__last_name']: scaled_grade})

        return points_and_developers


class GraphIntervals(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    difficulty = models.SmallIntegerField("Difficulty", default=0)
    priority = models.SmallIntegerField("Priority", default=0)
    lower_bound = models.IntegerField("Lower Bound", default=-1)
    upper_bound = models.IntegerField("Upper Bound", default=-1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['difficulty', 'priority'], name='name of constraint')
        ]

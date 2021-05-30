import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tps.settings")
django.setup()
from tasks.models import *
from django.contrib.auth.models import User
from datetime import date, timedelta, datetime


# Worth noting that the create operations of different models should be done in this order
# due to the foreign key references between some models, which also explains why the scope is shared.

supers = []
supers.append(User.objects.create_superuser('super1', password='super1password', email=''))
for super in supers:
    super.save()

dev_users = []
dev_users.append(User.objects.create_user(username='dev1', password='dev1password'))
dev_users.append(User.objects.create_user(username='dev2', password='dev2password'))
dev_users.append(User.objects.create_user(username='dev3', password='dev3password'))
dev_users.append(User.objects.create_user(username='dev4', password='dev4password'))
dev_users.append(User.objects.create_user(username='dev5', password='dev5password'))
dev_users.append(User.objects.create_user(username='dev6', password='dev6password'))
for user in dev_users:
    user.save()


courses = []
courses.append(Course(course='SE 302',section=1,year = 2020, term=2, number_of_students=40, team_weight=60, ind_weight=40))
courses.append(Course(course='CE 350',section=1,year = 2020, term=2, number_of_students=40, team_weight=60, ind_weight=40))
for course in courses:
    course.create_course_name()
    course.save()

milestones = []
four_weeks = timedelta(weeks=4)
eight_weeks = timedelta(weeks=8)
four_weeks_from_now = datetime.now() + four_weeks
four_weeks_from_today = four_weeks_from_now.date()
eight_weeks_from_now = datetime.now() + eight_weeks
eight_weeks_from_today = eight_weeks_from_now.date()
milestones.append(Milestone(course=courses[0], name='Milestone1-SE 302', description='Milestone1-SE 302 Description', due = four_weeks_from_today ))
milestones.append(Milestone(course=courses[0], name='Milestone2-SE 302', description='Milestone2-SE 302 Description', due = eight_weeks_from_today ))
milestones.append(Milestone(course=courses[0], name='Milestone3-SE 302', description='Milestone3-SE 302 Description', due = eight_weeks_from_today ))
milestones.append(Milestone(course=courses[1], name='Milestone1-CE 350', description='Milestone1-CE 350 Description', due = four_weeks_from_today ))
milestones.append(Milestone(course=courses[1], name='Milestone2-CE 350', description='Milestone2-CE 350 Description', due = eight_weeks_from_today ))
for milestone in milestones:
    milestone.save()

teams = []
teams.append(Team(course=courses[0], name='Team1-SE 3-2', github='fillertext'))
teams.append(Team(course=courses[0], name='Team2-SE 3-2', github='fillertext'))
teams.append(Team(course=courses[1], name='Team1-SE 3-2', github='fillertext'))
for team in teams:
    team.save()

developers = []
developers.append(Developer(id='100', user=dev_users[0]))
developers.append(Developer(id='101', user=dev_users[1]))
developers.append(Developer(id='102', user=dev_users[2]))
developers.append(Developer(id='103', user=dev_users[3]))
developers.append(Developer(id='104', user=dev_users[4]))
developers.append(Developer(id='105', user=dev_users[5]))
for developer in developers:
    developer.save()

dev_team_relations = []
dev_team_relations.append(DeveloperTeam(developer=developers[0], team=teams[0]))
dev_team_relations.append(DeveloperTeam(developer=developers[1], team=teams[0]))
dev_team_relations.append(DeveloperTeam(developer=developers[2], team=teams[1]))
dev_team_relations.append(DeveloperTeam(developer=developers[3], team=teams[1]))
dev_team_relations.append(DeveloperTeam(developer=developers[4], team=teams[1]))
dev_team_relations.append(DeveloperTeam(developer=developers[5], team=teams[2]))
for dev_team_relation in dev_team_relations:
    dev_team_relation.save()


two_weeks = timedelta(weeks=2)
two_weeks_from_now = datetime.now() + two_weeks
two_weeks_from_today = two_weeks_from_now.date()
tasks = []
tasks.append(Task(
    milestone=milestones[0],
    assignee=developers[0],
    team=teams[0],
    title='Task0 brief name',
    description='Task0 description',
    due=two_weeks_from_today
                 ))
tasks.append(Task(
    milestone=milestones[0],
    assignee=developers[1],
    team=teams[0],
    title='Task1 brief name',
    description='Task1 description',
    due=two_weeks_from_today
                 ))
tasks.append(Task(
    milestone=milestones[0],
    assignee=developers[0],
    team=teams[0],
    title='Task2 brief name',
    description='Task2 description',
    due=two_weeks_from_today
                 ))

for task in tasks:
    task.save()
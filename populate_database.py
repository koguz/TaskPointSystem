import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tps.settings")
django.setup()
from tasks.models import *
from django.contrib.auth.models import User, Permission
from datetime import date, timedelta
from django.utils import timezone

# Worth noting that the create operations of different models should be done in this order
# due to the foreign key references between some models, which also explains why the scope is shared.

# --- Superuser ---
admin = User.objects.create_superuser('admin', password='adminpassword', email='admin@tps.local')

# --- Lecturer user + Lecturer model ---
lec_user = User.objects.create_user(username='lecturer1', password='lecturer1password',
                                    first_name='John', last_name='Smith', email='lecturer1@tps.local')
lecturer = Lecturer(user=lec_user)
lecturer.save()
for codename in ['add_developer', 'add_mastercourse', 'add_team', 'add_milestone']:
    lec_user.user_permissions.add(Permission.objects.get(codename=codename))

# --- Developer users ---
dev_users = []
dev_names = [
    ('Alice', 'Brown'),
    ('Bob', 'Davis'),
    ('Carol', 'Evans'),
    ('Dave', 'Garcia'),
    ('Eve', 'Harris'),
    ('Frank', 'Johnson'),
]
for i, (first, last) in enumerate(dev_names, start=1):
    user = User.objects.create_user(username=f'dev{i}', password=f'dev{i}password',
                                    first_name=first, last_name=last)
    dev_users.append(user)

# --- Master Courses ---
mc_se = MasterCourse(code='SE 302', name='Software Engineering')
mc_se.save()
mc_ce = MasterCourse(code='CE 350', name='Computer Engineering Project')
mc_ce.save()

# --- Courses ---
course_se = Course(masterCourse=mc_se, lecturer=lecturer, academic_year='2024-2025', semester=Course.SEMESTER_SPRING,
                   group_weight=60, individual_weight=40)
course_se.save()
course_ce = Course(masterCourse=mc_ce, lecturer=lecturer, academic_year='2024-2025', semester=Course.SEMESTER_SPRING,
                   group_weight=50, individual_weight=50)
course_ce.save()

# --- Milestones ---
four_weeks_from_today = date.today() + timedelta(weeks=4)
eight_weeks_from_today = date.today() + timedelta(weeks=8)
twelve_weeks_from_today = date.today() + timedelta(weeks=12)

milestones = []
milestones.append(Milestone(course=course_se, name='Requirements', description='Requirements analysis and SRS document', weight=30, due=four_weeks_from_today))
milestones.append(Milestone(course=course_se, name='Design', description='System design and architecture', weight=30, due=eight_weeks_from_today))
milestones.append(Milestone(course=course_se, name='Implementation', description='Coding and testing', weight=40, due=twelve_weeks_from_today))
milestones.append(Milestone(course=course_ce, name='Proposal', description='Project proposal and feasibility study', weight=40, due=four_weeks_from_today))
milestones.append(Milestone(course=course_ce, name='Final Delivery', description='Final project delivery and demo', weight=60, due=twelve_weeks_from_today))
for m in milestones:
    m.save()

# --- Teams ---
team1 = Team(course=course_se, name='Alpha Team', github='https://github.com/alpha-team', supervisor=lecturer)
team1.save()
team2 = Team(course=course_se, name='Beta Team', github='https://github.com/beta-team', supervisor=lecturer)
team2.save()
team3 = Team(course=course_ce, name='Gamma Team', github='https://github.com/gamma-team', supervisor=lecturer)
team3.save()

# --- Developers ---
developers = []
for user in dev_users:
    dev = Developer(user=user)
    dev.save()
    developers.append(dev)

# Assign developers to teams (M2M)
# Team Alpha: dev1 (Alice), dev2 (Bob)
developers[0].team.add(team1)
developers[1].team.add(team1)
# Team Beta: dev3 (Carol), dev4 (Dave), dev5 (Eve)
developers[2].team.add(team2)
developers[3].team.add(team2)
developers[4].team.add(team2)
# Team Gamma: dev6 (Frank) + dev1 (Alice is in two teams)
developers[5].team.add(team3)
developers[0].team.add(team3)

# Developer-course section assignments
DeveloperCourse.objects.update_or_create(
    developer=developers[0], course=course_se, defaults={"section": 1, "description": "Monday mornings"}
)
DeveloperCourse.objects.update_or_create(
    developer=developers[1], course=course_se, defaults={"section": 1, "description": "Monday mornings"}
)
DeveloperCourse.objects.update_or_create(
    developer=developers[2], course=course_se, defaults={"section": 2, "description": "Wednesday afternoons"}
)
DeveloperCourse.objects.update_or_create(
    developer=developers[3], course=course_se, defaults={"section": 2, "description": "Wednesday afternoons"}
)
DeveloperCourse.objects.update_or_create(
    developer=developers[4], course=course_se, defaults={"section": 2, "description": "Wednesday afternoons"}
)
DeveloperCourse.objects.update_or_create(
    developer=developers[5], course=course_ce, defaults={"section": 1, "description": "Friday mornings"}
)
DeveloperCourse.objects.update_or_create(
    developer=developers[0], course=course_ce, defaults={"section": 3, "description": "Cross-section team"}
)

# --- MasterTasks + Tasks ---
two_weeks_from_today = date.today() + timedelta(weeks=2)
three_weeks_from_today = date.today() + timedelta(weeks=3)

# Task 1: Alice's task in Alpha Team
mt1 = MasterTask(milestone=milestones[0], owner=developers[0], team=team1, difficulty=2, status=2,
                 opened=timezone.now())
mt1.save()
Task(masterTask=mt1, title='Write use case diagrams', description='Create UML use case diagrams for the main system features',
     promised_date=two_weeks_from_today, priority=2, version=1).save()

# Task 2: Bob's task in Alpha Team
mt2 = MasterTask(milestone=milestones[0], owner=developers[1], team=team1, difficulty=1, status=2,
                 opened=timezone.now())
mt2.save()
Task(masterTask=mt2, title='Gather requirements from stakeholders', description='Interview stakeholders and document functional requirements',
     promised_date=two_weeks_from_today, priority=3, version=1).save()

# Task 3: Another task for Alice in Alpha Team
mt3 = MasterTask(milestone=milestones[0], owner=developers[0], team=team1, difficulty=3, status=1,
                 opened=timezone.now())
mt3.save()
Task(masterTask=mt3, title='Draft SRS document', description='Write the Software Requirements Specification document',
     promised_date=three_weeks_from_today, priority=2, version=1).save()

# Task 4: Carol's task in Beta Team
mt4 = MasterTask(milestone=milestones[0], owner=developers[2], team=team2, difficulty=2, status=2,
                 opened=timezone.now())
mt4.save()
Task(masterTask=mt4, title='Setup project repository', description='Initialize git repo, add README and CI pipeline',
     promised_date=two_weeks_from_today, priority=2, version=1).save()

# Task 5: Frank's task in Gamma Team
mt5 = MasterTask(milestone=milestones[3], owner=developers[5], team=team3, difficulty=2, status=1,
                 opened=timezone.now())
mt5.save()
Task(masterTask=mt5, title='Write project proposal', description='Draft the project proposal document with scope and timeline',
     promised_date=three_weeks_from_today, priority=2, version=1).save()

print("Database populated successfully!")
print()
print("Accounts created:")
print("  Admin:     admin / adminpassword")
print("  Lecturer:  lecturer1 / lecturer1password")
print("  Students:  dev1..dev6 / dev<N>password")

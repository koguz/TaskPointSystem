import csv
from datetime import datetime
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import Group, User
from django.contrib.auth.forms import PasswordChangeForm
from django.http.response import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils.html import strip_tags


from tasks.models import *
from .forms import CommentForm, CourseForm, MasterCourseForm, MilestoneForm, TaskForm, TeamFormStd, EmailChangeForm


# Create your views here.

def saveLog(mt: MasterTask, message, gizli: bool = False):
    l = MasterTaskLog()
    l.mastertask = mt
    l.taskstatus = mt.getStatus()
    l.log = message
    l.gizli = gizli
    l.save()


def _task_url(task_id):
    return f"{settings.SITE_URL}/tasks/{task_id}"


def _send_notification_email(subject, plain_message, recipient_list, html_message=None):
    if not getattr(settings, "EMAIL_NOTIFICATIONS_ENABLED", False):
        return 0
    if not recipient_list:
        return 0
    return send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        html_message=html_message
    )


AVATAR_PRESETS = [
    ("penguin", "Penguin"),
    ("flower", "Flower"),
    ("butterfly", "Butterfly"),
    ("cat", "Cat"),
    ("dog", "Dog"),
    ("fox", "Fox"),
    ("panda", "Panda"),
    ("owl", "Owl"),
    ("turtle", "Turtle"),
    ("bee", "Bee"),
    ("dolphin", "Dolphin"),
    ("whale", "Whale"),
    ("rabbit", "Rabbit"),
    ("frog", "Frog"),
    ("ladybug", "Ladybug"),
    ("snail", "Snail"),
    ("mushroom", "Mushroom"),
    ("cactus", "Cactus"),
    ("sunflower", "Sunflower"),
    ("rose", "Rose"),
    ("maple", "Maple"),
    ("rainbow", "Rainbow"),
    ("moon", "Moon"),
    ("star", "Star"),
]


def _avatar_options():
    return [
        {
            "label": label,
            "url": static(f"tasks/avatars/{slug}.svg"),
        }
        for slug, label in AVATAR_PRESETS
    ]


def _avatar_url_set():
    return {static(f"tasks/avatars/{slug}.svg") for slug, _ in AVATAR_PRESETS}


def _default_avatar_url():
    return static(f"tasks/avatars/{AVATAR_PRESETS[0][0]}.svg")


def _sanitize_developer_avatar(dev: Developer):
    allowed_urls = _avatar_url_set()
    if dev.photoURL not in allowed_urls:
        dev.photoURL = _default_avatar_url()
        dev.save(update_fields=["photoURL"])
    return dev


def _developer_teams_queryset(dev: Developer, active_only: bool = False):
    teams = dev.team.select_related("course", "course__masterCourse").order_by("-pk")
    if active_only:
        teams = teams.filter(course__active=True)
    return teams


def _developer_default_team(dev: Developer):
    team = _developer_teams_queryset(dev, active_only=True).first()
    if team is not None:
        return team
    return _developer_teams_queryset(dev).first()


def _has_revision_request(mastertask: MasterTask, task: Task):
    if mastertask.status not in (1, 3):
        return False
    return Vote.objects.filter(
        task=task,
        status=mastertask.status,
        vote=False
    ).exists()


def _parse_positive_int(value, fallback):
    try:
        parsed = int(str(value).strip())
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return fallback


def _parse_student_section_meta(fields, section_index, description_index, default_section, default_description, line_no, errors):
    section = default_section
    description = default_description

    if len(fields) > section_index and fields[section_index]:
        parsed_section = _parse_positive_int(fields[section_index], None)
        if parsed_section is None:
            errors.append(f"Line {line_no}: section must be a positive integer.")
        else:
            section = parsed_section

    if len(fields) > description_index and fields[description_index]:
        description = fields[description_index]

    return section, description


def _parse_manual_team_rows(raw_text, default_section, default_description):
    rows = []
    errors = []
    for line_no, line in enumerate((raw_text or "").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        fields = [f.strip() for f in stripped.split(",")]
        if len(fields) < 4:
            errors.append(f"Line {line_no}: expected 'Team Name, Student ID, Name, Surname'.")
            continue
        team_name, student_id, first_name, last_name = fields[:4]
        if not team_name or not student_id or not first_name or not last_name:
            errors.append(f"Line {line_no}: all four values must be non-empty.")
            continue
        section, description = _parse_student_section_meta(
            fields, 4, 5, default_section, default_description, line_no, errors
        )
        rows.append({
            "line_no": line_no,
            "team_name": team_name,
            "student_id": student_id,
            "first_name": first_name,
            "last_name": last_name,
            "section": section,
            "description": description,
        })
    return rows, errors


def _parse_random_team_rows(raw_text, default_section, default_description):
    rows = []
    errors = []
    for line_no, line in enumerate((raw_text or "").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        fields = [f.strip() for f in stripped.split(",")]
        if len(fields) < 3:
            errors.append(f"Line {line_no}: expected 'Student ID, Name, Surname'.")
            continue
        student_id, first_name, last_name = fields[:3]
        if not student_id or not first_name or not last_name:
            errors.append(f"Line {line_no}: all three values must be non-empty.")
            continue
        section, description = _parse_student_section_meta(
            fields, 3, 4, default_section, default_description, line_no, errors
        )
        rows.append({
            "line_no": line_no,
            "student_id": student_id,
            "first_name": first_name,
            "last_name": last_name,
            "section": section,
            "description": description,
        })
    return rows, errors


def _course_team_assignments(course: Course):
    teams = Team.objects.filter(course=course).order_by("name", "pk")
    enrollment_map = {
        enrollment.developer_id: enrollment
        for enrollment in DeveloperCourse.objects.filter(course=course)
    }
    team_map = {}
    for team in teams:
        developers = list(
            Developer.objects.filter(team=team).select_related("user").order_by(
                "user__first_name", "user__last_name", "user__username"
            )
        )
        team_map[team.name] = []
        for developer in developers:
            enrollment = enrollment_map.get(developer.pk)
            team_map[team.name].append({
                "developer": developer,
                "section": enrollment.section if enrollment else None,
                "description": enrollment.description if enrollment else "",
            })
    return team_map


def _course_section_score_rows(course: Course):
    teams = list(
        Team.objects.filter(course=course).prefetch_related("developer_set__user")
    )
    team_by_developer = {}
    for team in teams:
        for developer in team.developer_set.all():
            if developer.pk not in team_by_developer:
                team_by_developer[developer.pk] = team

    enrollments = {
        enrollment.developer_id: enrollment
        for enrollment in DeveloperCourse.objects.filter(course=course).select_related("developer__user")
    }

    developer_ids = set(team_by_developer.keys()) | set(enrollments.keys())
    developers = {
        developer.pk: developer
        for developer in Developer.objects.filter(pk__in=developer_ids).select_related("user")
    }

    rows = []
    for developer_id in developer_ids:
        developer = developers[developer_id]
        enrollment = enrollments.get(developer_id)
        team = team_by_developer.get(developer_id)
        score = developer.get_project_grade(team.pk) if team is not None else 0
        rows.append({
            "student_id": developer.user.username,
            "first_name": developer.user.first_name,
            "last_name": developer.user.last_name,
            "team_name": team.name if team is not None else "",
            "section": enrollment.section if enrollment is not None else None,
            "section_description": enrollment.description if enrollment is not None else "",
            "score": score,
        })

    rows.sort(
        key=lambda row: (
            row["section"] is None,
            row["section"] if row["section"] is not None else 10 ** 9,
            row["student_id"]
        )
    )

    section_rows = {}
    for row in rows:
        section_key = row["section"] if row["section"] is not None else "Unassigned"
        if section_key not in section_rows:
            section_rows[section_key] = []
        section_rows[section_key].append(row)
    return rows, section_rows


def _get_or_create_student_developer(student_id, first_name, last_name):
    user = User.objects.filter(username=student_id).first()
    if user is None:
        user = User.objects.create_user(student_id, None, student_id)
        user.first_name = first_name
        user.last_name = last_name
        group, _ = Group.objects.get_or_create(name="student")
        user.groups.add(group)
        user.save()
        developer = Developer.objects.create(user=user, photoURL=_default_avatar_url())
        return developer

    developer, created = Developer.objects.get_or_create(
        user=user,
        defaults={"photoURL": _default_avatar_url()}
    )
    if created:
        return developer

    updated = False
    if not user.first_name and first_name:
        user.first_name = first_name
        updated = True
    if not user.last_name and last_name:
        user.last_name = last_name
        updated = True
    if updated:
        user.save(update_fields=["first_name", "last_name"])
    return developer


def _next_default_team_name(existing_team_names, start_no):
    team_no = start_no
    while True:
        team_name = f"Team {team_no}"
        if team_name not in existing_team_names:
            return team_name, team_no + 1
        team_no += 1


def _balanced_group_sizes(total_students, target_size):
    if total_students <= 0:
        return []
    if target_size <= 0:
        target_size = 1
    if total_students <= target_size:
        return [total_students]

    group_count = total_students // target_size
    remainder = total_students % target_size

    if remainder > group_count:
        group_count += 1
        base_size = total_students // group_count
        extra = total_students % group_count
        return [base_size + 1] * extra + [base_size] * (group_count - extra)

    sizes = [target_size] * group_count
    for idx in range(remainder):
        sizes[idx] += 1
    return sizes


def _build_team_points_breakdown(team: Team, current_user=None):
    milestones = list(team.course.milestone_set.all().order_by("due", "pk"))
    developers = list(
        team.developer_set.select_related("user").order_by(
            "user__first_name", "user__last_name", "user__username"
        )
    )
    developer_count = len(developers)

    accepted_points_lookup = {}
    accepted_tasks = MasterTask.objects.filter(
        team=team,
        status=5,
        milestone__in=milestones
    )
    for mastertask in accepted_tasks:
        key = (mastertask.owner_id, mastertask.milestone_id)
        accepted_points_lookup[key] = accepted_points_lookup.get(key, 0) + mastertask.get_points()

    milestone_rows = []
    overall_planned_points = 0
    overall_accepted_points = 0
    team_weighted_score = 0.0
    for milestone in milestones:
        total_points = team.get_all_milestone_points(milestone)
        accepted_points = team.get_all_accepted_points(milestone)
        team_score = round((accepted_points / total_points) * 100) if total_points > 0 else 0
        weighted_team_score = team_score * (milestone.weight / 100)

        overall_planned_points += total_points
        overall_accepted_points += accepted_points
        team_weighted_score += weighted_team_score
        milestone_rows.append({
            "milestone": milestone,
            "total_points": total_points,
            "accepted_points": accepted_points,
            "team_score": team_score,
            "weighted_team_score": weighted_team_score,
        })

    overall_team_score = round((overall_accepted_points / overall_planned_points) * 100) if overall_planned_points > 0 else 0
    team_component = team_weighted_score * (team.course.group_weight / 100)

    developer_rows = []
    developers_summary = {}
    for developer in developers:
        milestone_scores = []
        milestone_score_map = {}
        individual_weighted_score = 0.0

        for milestone_row in milestone_rows:
            milestone = milestone_row["milestone"]
            planned_points_per_developer = (
                milestone_row["total_points"] / developer_count
                if developer_count > 0 else 0
            )
            accepted_points = accepted_points_lookup.get((developer.pk, milestone.pk), 0)

            if planned_points_per_developer > 0:
                developer_score = round((accepted_points / planned_points_per_developer) * 100)
                if developer_score > 100:
                    developer_score = 100
            else:
                developer_score = 0

            weighted_individual_score = developer_score * (milestone.weight / 100)
            individual_weighted_score += weighted_individual_score
            milestone_scores.append({
                "milestone": milestone,
                "accepted_points": accepted_points,
                "planned_points_per_developer": planned_points_per_developer,
                "score": developer_score,
                "weighted_score": weighted_individual_score,
            })
            milestone_score_map[milestone.name] = developer_score

        individual_component = individual_weighted_score * (team.course.individual_weight / 100)
        project_score = round(team_component + individual_component)
        row = {
            "developer": developer,
            "milestone_scores": milestone_scores,
            "individual_component": individual_component,
            "project_score": project_score,
            "is_current_user": bool(current_user and developer.user_id == current_user.id),
        }
        developer_rows.append(row)
        developers_summary[developer] = [project_score, milestone_score_map]

    return {
        "milestones": milestones,
        "developers": developers,
        "milestone_rows": milestone_rows,
        "developer_rows": developer_rows,
        "developers_summary": developers_summary,
        "overall_planned_points": overall_planned_points,
        "overall_accepted_points": overall_accepted_points,
        "overall_team_score": overall_team_score,
        "team_weighted_score": team_weighted_score,
        "team_component": team_component,
    }

def _reject_overdue_tasks(teams):
    from datetime import date
    today = date.today()
    overdue_tasks = MasterTask.objects.filter(
        team__in=teams,
        status__lt=4
    ).select_related('milestone')

    # Bulk reject tasks whose milestone is past due
    milestone_overdue = overdue_tasks.filter(milestone__due__lt=today)
    for mt in milestone_overdue:
        mt.status = 4
        mt.save(update_fields=['status'])
        saveLog(mt, "Task is rejected because milestone is due.")

    # Bulk reject tasks whose promised date is past due
    from django.db.models import Max, Subquery, OuterRef
    latest_promised = Task.objects.filter(
        masterTask=OuterRef('pk')
    ).order_by('-pk').values('promised_date')[:1]

    promised_overdue = overdue_tasks.annotate(
        latest_promised_date=Subquery(latest_promised)
    ).filter(latest_promised_date__lt=today)

    for mt in promised_overdue:
        mt.status = 4
        mt.save(update_fields=['status'])
        saveLog(mt, "Task is rejected because due date has passed.")


@login_required
def index(request):
    # redirect to another page for lecturer!
    try:
        d: Developer = Developer.objects.get(user=request.user)
        _reject_overdue_tasks(d.team.all())
        default_team = _developer_default_team(d)
        if default_team is not None:
            return redirect('team_view', default_team.pk)
        return redirect('my_details')
    except ObjectDoesNotExist:
        try:
            l: Lecturer = Lecturer.objects.get(user=request.user)
            return redirect('lecturer_view')
        except ObjectDoesNotExist:
            return redirect('logout')


@login_required
def update_view(request):
    return render(request, 'tasks/updates.html')


@login_required
def team_view(request, team_id):
    d: Developer = Developer.objects.get(user=request.user)
    all_teams = _developer_teams_queryset(d)
    if not all_teams.exists():
        return redirect('my_details')

    active_teams = _developer_teams_queryset(d, active_only=True)
    t = get_object_or_404(
        Team.objects.select_related("course", "course__masterCourse"),
        pk=team_id
    )

    if not all_teams.filter(pk=t.pk).exists():
        fallback_team = _developer_default_team(d)
        if fallback_team is not None:
            return redirect('team_view', fallback_team.pk)
        return redirect('my_details')

    teams_for_selector = active_teams if active_teams.exists() and t.course.active else all_teams

    points_data = _build_team_points_breakdown(t, current_user=request.user)
    devs = points_data["developers"]
    milestone = t.course.get_current_milestone()
    task_qs = MasterTask.objects.filter(team=t).order_by("-pk")
    task_paginator = Paginator(task_qs, 10)
    tasks_page = task_paginator.get_page(request.GET.get("page"))

    context = {
        'page_title': 'Team Home',
        'tasks_page': tasks_page,
        'team': t,
        'course_active': t.course.active,
        'devs': devs,
        'milestone': milestone,
        'teams': teams_for_selector,
        'developers': points_data["developers_summary"],
    }
    return render(request, 'tasks/index.html', context)


@login_required
def team_points_detail(request, team_id):
    try:
        d: Developer = Developer.objects.get(user=request.user)
    except ObjectDoesNotExist:
        try:
            Lecturer.objects.get(user=request.user)
            return redirect('lecturer_view')
        except ObjectDoesNotExist:
            return redirect('logout')
    t = get_object_or_404(
        Team.objects.select_related("course", "course__masterCourse"),
        pk=team_id
    )
    if not _developer_teams_queryset(d).filter(pk=t.pk).exists():
        fallback_team = _developer_default_team(d)
        if fallback_team is not None:
            return redirect('team_points_detail', fallback_team.pk)
        return redirect('my_details')

    points_data = _build_team_points_breakdown(t, current_user=request.user)
    context = {
        'page_title': 'Team Points Breakdown',
        'team': t,
        'is_lecturer_view': False,
        **points_data,
    }
    return render(request, 'tasks/team_points_detail.html', context)


@login_required
def edit_task(request, task_id):
    mt: MasterTask = get_object_or_404(MasterTask, pk=task_id)
    t: Task = Task.objects.all().filter(
        masterTask=mt).order_by('pk').reverse()[0]
    d: Developer = Developer.objects.get(user=request.user)
    tm = mt.team
    if mt.owner != d:  # return to team view if the owner of the task is not this user
        return redirect('team_view', tm.pk)
    if not tm.course.active:
        return redirect('view_task', task_id)
    # return to team view if the master task is not 1 (proposed)
    if mt.status != 1:
        return redirect('team_view', tm.pk)
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task: Task = form.save(commit=False)
            task.pk = None
            task.masterTask = mt
            task.version = t.version + 1
            task.save()

            devs = Developer.objects.all().filter(team=tm)

            receivers = []

            for developer in devs:
                if developer != d:
                    receivers.append(developer.user.email)

            subject = 'TPS:Notification || A task has been edited!'
            contentList = [
                'Edited by: ' + str(mt.owner),
                'Title: ' + task.title,
                'Description: ' + task.description,
                'Priority: ' + task.getPriority(),
                'Due date: ' + str(task.promised_date)
            ]
            url = _task_url(task.masterTask_id)

            html_message = render_to_string('tasks/email_template.html',
            {'title': 'A task has been edited.', 'contentList': contentList, 'url': url, 'background_color': '#003399'})

            plain_message = strip_tags(html_message)
            
            saveLog(mt, "Task is edited by " + str(d) + ".")
            _send_notification_email(subject, plain_message, receivers, html_message=html_message)
            

            return redirect('view_task', task_id)
        else: 
            return redirect('team_view', tm.pk)
    else:
        form = TaskForm(instance=t)
        context = {
            'page_title': 'Edit task',
            'form': form, 
            'mastertask': mt,
            'team': tm
        }
        return render(request, "tasks/task_edit.html", context)

@login_required
def create_task(request, team_id):
    d = Developer.objects.get(user=request.user)
    t:Team = Team.objects.get(pk=team_id)
    if not _developer_teams_queryset(d).filter(pk=t.pk).exists():
        fallback_team = _developer_default_team(d)
        if fallback_team is not None:
            return redirect('team_view', fallback_team.pk)
        return redirect('my_details')

    if not t.course.active:
        fallback_team = _developer_default_team(d)
        if fallback_team is not None:
            return redirect('team_view', fallback_team.pk)
        return redirect('my_details')

    milestone = t.course.get_current_milestone() #Milestone.objects.all().filter(course=t.course).order_by('due')[0]
    if milestone is None:
        return redirect('team_view', t.pk)

    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            mastertask = MasterTask()            
            mastertask.milestone = milestone
            mastertask.owner = d
            mastertask.team = t
            mastertask.save()
            task:Task = form.save(commit=False)
            task.masterTask = mastertask 
            task.save()

            devs = Developer.objects.all().filter(team=t)

            receivers = []

            for developer in devs:
                if developer != d:
                    receivers.append(developer.user.email)

            contentList = [
                'Creator: ' + str(mastertask.owner),
                'Title: ' + task.title,
                'Description: ' + task.description,
                'Priority: ' + task.getPriority(),
                'Due date: ' + str(task.promised_date)
            ]

            subject = 'TPS:Notification || A task has been created'

            url = _task_url(task.masterTask_id)

            html_message = render_to_string('tasks/email_template.html',
            {'title':'A task has been created!', 'contentList':contentList, 'url': url, 'background_color': '#003399'})

            plain_message = strip_tags(html_message)
            
            saveLog(mastertask, "Task is created by " + str(d) + ".")
            _send_notification_email(subject, plain_message, receivers, html_message=html_message)
            
            
            return redirect('team_view', team_id)
        else:
            context = {
                'page_title': 'Create New Task',
                'form': form,
                'milestone': milestone,
                'team': t
            }
            return render(request, "tasks/task_create.html", context)
            # return redirect('team_view')
    else:
        form = TaskForm()
        context = {
            'page_title': 'Create New Task',
            'form': form, 
            'milestone': milestone,
            'team': t
        } 
        return render(request, "tasks/task_create.html", context)

@login_required 
def complete_task(request, task_id):
    mt:MasterTask = get_object_or_404(MasterTask, pk=task_id)
    t:Task = Task.objects.all().filter(masterTask=mt).order_by('pk').reverse()[0]
    d:Developer = Developer.objects.get(user=request.user)
    tm = mt.team
    if mt.owner != d:
        return redirect('team_view', tm.pk)
    if not tm.course.active:
        return redirect('view_task', task_id)
    if request.method != 'POST':
        return redirect('team_view', tm.pk)

    if mt.status not in (2, 3):
        return redirect('view_task', task_id)

    completion_update_mode = mt.status == 3
    if completion_update_mode and not _has_revision_request(mt, t):
        return redirect('view_task', task_id)

    completion_summary = request.POST.get("completion_summary", "").strip()
    completion_file_url = request.POST.get("completion_file_url", "").strip()
    if not completion_summary or not completion_file_url:
        return redirect('view_task', task_id)

    try:
        difficulty_value = int(request.POST.get("difficulty", mt.difficulty))
    except (TypeError, ValueError):
        difficulty_value = mt.difficulty
    if difficulty_value not in [1, 2, 3]:
        difficulty_value = mt.difficulty

    mt.status = 3
    mt.difficulty = difficulty_value
    mt.used_ai = 'used_ai' in request.POST
    mt.ai_usage = ','.join(request.POST.getlist('ai_usage')) if mt.used_ai else ''
    mt.completed = datetime.now()
    mt.save()

    completion_comment = Comment(
        owner=request.user,
        mastertask=mt,
        task=t,
        body=completion_summary,
        file_url=completion_file_url,
        is_completion_update=True
    )
    completion_comment.save()

    if completion_update_mode:
        Vote.objects.filter(task=t, status=3).delete()
        saveLog(mt, "Completion update submitted by " + str(d) + ". Completed-state votes are reset.")
    else:
        saveLog(mt, "Task is completed by " + str(d) + ".")

    difficulty_label = mt.getDifficulty()

    devs = Developer.objects.all().filter(team=tm)
    receivers = []
    for developer in devs:
        if developer != d:
            receivers.append(developer.user.email)

    if completion_update_mode:
        subject = 'TPS:Notification || A completion update has been submitted'
        title = 'A completion update has been submitted!'
    else:
        subject = 'TPS:Notification || A task has been completed'
        title = 'A task has been completed!'

    contentList = [
        'Creator: ' + str(mt.owner),
        'Title: ' + t.title,
        'Description: ' + t.description,
        'Priority: ' + t.getPriority(),
        'Difficulty: ' + difficulty_label,
        'Used Generative AI: ' + ('Yes (' + mt.ai_usage + ')' if mt.used_ai else 'No'),
        'Completion Summary: ' + completion_summary,
        'Git Commit or File URL: ' + completion_file_url,
        'Due date: '+ str(t.promised_date)
    ]

    url = _task_url(t.masterTask_id)
    html_message = render_to_string('tasks/email_template.html',
    {'title': title, 'contentList': contentList, 'url':url, 'background_color': '#003399'})
    plain_message = strip_tags(html_message)
    _send_notification_email(subject, plain_message, receivers, html_message=html_message)

    return redirect('view_task', task_id)

@login_required 
def edit_team(request, team_id):
    d:Developer = Developer.objects.get(user=request.user)
    t:Team = Team.objects.get(pk=team_id)
    if not _developer_teams_queryset(d).filter(pk=t.pk).exists():
        fallback_team = _developer_default_team(d)
        if fallback_team is not None:
            return redirect('team_view', fallback_team.pk)
        return redirect('my_details')
    if not t.course.active:
        return redirect('team_view', team_id)
    if request.method == 'POST':
        form = TeamFormStd(request.POST)
        if form.is_valid():
            tnew = form.save(commit=False)
            tnew.pk = t.pk
            tnew.supervisor = t.supervisor
            tnew.course = t.course
            tnew.save()
            return redirect('team_view', team_id)
    else:
        form = TeamFormStd(instance=t)
    context = {
        'page_title': 'Edit Team Information',
        'form': form,
        'team': t
    }
    return render(request, "tasks/team_edit_std.html", context)


@login_required 
def like_task(request,task_id, liked):
    mt:MasterTask = get_object_or_404(MasterTask, pk=task_id)
    d:Developer = Developer.objects.get(user=request.user)
    if not mt.team.course.active:
        return redirect('view_task', task_id)
    
    if mt.owner == d:
        return redirect('team_view', mt.team.pk)
    try:
        # if like object exists, toggle like
        like = Like.objects.get(owner=d, mastertask=mt)
        if liked == 1 and like.liked:
            like.delete() 
            saveLog(mt, "Like removed by "+ str(d) + ".", True)
        elif liked == 0 and not like.liked:
            like.delete() 
            saveLog(mt, "Dislike removed by "+ str(d) + ".", True)
        elif liked == 1 and not like.liked:
            like.liked = True 
            like.save() 
            saveLog(mt, "Task liked by "+ str(d) + ".", True)
        elif liked == 0 and like.liked: 
            like.liked = False 
            like.save() 
            saveLog(mt, "Task disliked by "+ str(d) + ".", True)
    except ObjectDoesNotExist:
        like = Like()
        like.owner = d 
        like.mastertask = mt 
        if liked == 1:
            like.liked = True 
            saveLog(mt, "Task liked by "+ str(d) + ".", True)
        else:
            like.liked = False 
            saveLog(mt, "Task disliked by "+ str(d) + ".", True)
        like.save() 
    return redirect('view_task', task_id)



@login_required
def view_task(request, task_id):
    mt:MasterTask = get_object_or_404(MasterTask, pk=task_id)
    t:Task = Task.objects.all().filter(masterTask=mt).order_by('pk').reverse()[0]
    try:
        d:Developer = Developer.objects.get(user=request.user)
    except ObjectDoesNotExist:
        try:
            Lecturer.objects.get(user=request.user)
            return redirect('lecturer_view_task', task_id)
        except ObjectDoesNotExist:
            return redirect('logout')

    if mt.team in d.team.all():
        tm = mt.team
        task_owner: Developer = mt.owner
        if request.method == 'POST':
            if not tm.course.active:
                return redirect('view_task', task_id)
            form = CommentForm(request.POST)
            if form.is_valid():
                comment:Comment = form.save(commit=False)
                comment.owner = request.user
                comment.mastertask = mt 
                comment.task = t 
                if len(Vote.objects.all().filter(task=t).filter(status=mt.status).filter(owner=d)) == 0:
                    if request.POST['approve'] == "Yes":
                        comment.approved = True
                        vote = Vote()
                        vote.owner = d
                        vote.task = t
                        vote.status = mt.status
                        vote.vote = True
                        vote.save()

                        subject = 'TPS:Notification || The task you created has received an approve vote.'
                        contentList = [
                            'Your task called ' + t.title + ' has received an aprove vote.',
                            'Approver: ' + str(d),
                            str(d) + '\'s comment: ' + comment.body,
                            'Priority: ' + t.getPriority(),
                            'Due date: ' + str(t.promised_date)
                        ]

                        url = _task_url(t.masterTask_id)
                        html_message = render_to_string('tasks/email_template.html',
                        {'title': 'A task has received an approve vote!', 'contentList': contentList, 'url': url, 'background_color': '#5cb85c'})

                        plain_message = strip_tags(html_message)
                        saveLog(mt, "Task received an approve vote by "+ str(d) + ".")
                        _send_notification_email(subject, plain_message, [task_owner.user.email], html_message=html_message)

                    elif request.POST['approve'] == "No":
                        comment.approved = False
                        vote = Vote()
                        vote.owner = d
                        vote.task = t
                        vote.status = mt.status
                        vote.vote = False
                        vote.save()

                        subject = 'TPS:Notification || The task you created has received a revision request.'
                        contentList = [
                            'Your task called ' + t.title + ' has received a revision request.',
                            'Requested by: ' + str(d),
                            str(d) + '\'s comment: ' + comment.body,
                            'Priority: ' + t.getPriority(),
                            'Due date: ' + str(t.promised_date)
                        ]
                        url = _task_url(t.masterTask_id)
                        html_message = render_to_string('tasks/email_template.html',
                        {'title':'A task has received a revision request.', 'contentList': contentList, 'url':url, 'background_color': '#ff2400'})

                        plain_message = strip_tags(html_message)
            
                        saveLog(mt, "Task received a revision request by "+ str(d) + ".")
                        _send_notification_email(subject, plain_message, [task_owner.user.email], html_message=html_message)
                comment.save()
                return redirect('view_task', task_id)
    
        form = CommentForm()
        comments = Comment.objects.all().filter(mastertask=mt).order_by('date').reverse()
        voted = len(Vote.objects.all().filter(task=t).filter(status=mt.status).filter(owner=d))
        v_app = len(Vote.objects.all().filter(task=t).filter(status=mt.status).filter(vote=True))
        v_den = len(Vote.objects.all().filter(task=t).filter(status=mt.status).filter(vote=False))
        reopen = False
        if mt.status == 1 and v_app > (len(mt.team.developer_set.all()) - 1) / 2:
            mt.status = 2
            mt.opened = datetime.now()
            mt.save()
            
            subject = 'TPS:Notification || The task you created is now in open state.'

            contentList = [
                'Your task called ' + t.title + ' is now in open state.',
                'Description: ' + t.description,
                'Priority: ' + t.getPriority(),
                'Due date: ' + str(t.promised_date)
            ]
            
            url = _task_url(t.masterTask_id)

            html_message = render_to_string('tasks/email_template.html',           
            {'title':'Your task is now in open state!','contentList': contentList, 'url':url, 'background_color': '#003399'})

            plain_message = strip_tags(html_message)

            saveLog(mt, "All approved. Task is now in open state.")
            _send_notification_email(subject, plain_message, [task_owner.user.email], html_message=html_message)
            
        elif mt.status == 3 and v_app > (len(mt.team.developer_set.all()) - 1) / 2:
            mt.status = 5
            mt.save()

            subject = 'TPS:Notification || The task you created is now accepted.'
            url = _task_url(t.masterTask_id)

            html_message = render_to_string('tasks/email_template.html',           
            {'title':'Your task is accepted!', 'contentList': ['Your task called ' + t.title + ' is now accepted.'],'url':url, 'background_color': '#003399' })

            plain_message = strip_tags(html_message)
            
            saveLog(mt, "All approved. Task is now accepted!")
            _send_notification_email(subject, plain_message, [task_owner.user.email], html_message=html_message)
            
        elif mt.status == 3 and v_den >= (len(mt.team.developer_set.all()) - 1) / 2:
            reopen = True 

        revision_requested = _has_revision_request(mt, t)
            
        try:
            liked = Like.objects.get(owner = d, mastertask = mt).liked
        except ObjectDoesNotExist:
            liked = None 

        logs = MasterTaskLog.objects.all().filter(mastertask=mt).filter(gizli=False).order_by('tarih').reverse()

        context = {
            'page_title': 'View Task',
            'mastertask': mt,
            'task': t, 
            'course_active': tm.course.active,
            'tp': mt.difficulty * t.priority,
            'form': form,
            'voted': voted,
            'mytask': mt.owner == d,
            'v_app': v_app,
            'v_den': v_den,
            'reopen': reopen, 
            'revision_requested': revision_requested,
            'liked': liked, 
            'comments': comments,
            'logs' : logs
        }
        return render(request, "tasks/task_view.html", context)
    else : 
        fallback_team = _developer_default_team(d)
        if fallback_team is not None:
            return redirect('team_view', fallback_team.pk)
        return redirect('my_details')


@login_required
@permission_required('tasks.add_developer')  # students don't have the right to do so... 
def lecturer_view(request):
    l:Lecturer = Lecturer.objects.get(user=request.user)
    mcourses = MasterCourse.objects.all()
    courses = Course.objects.filter(lecturer=l).order_by('-active', '-pk')
    context = {
        'page_title': 'Home', 
        'courses': courses,
        'mcourses': mcourses
    }
    return render(request, 'tasks/lecturer_index.html', context) 

def tpslogin(request):
    if request.method == 'POST':
        userid = request.POST['universityid']
        pwd = request.POST['tpspass']

        user = authenticate(request, username=userid, password=pwd)
        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            context = {
                'page_title': 'Login',
                'login_error': 'Login failed. Please contact Kaya Oğuz (kaya.oguz@ieu.edu.tr) if you are experiencing problems logging in.'
                }
            return render(request, 'tasks/login.html', context)
    else: 
        context = {
            'page_title': 'Login'
        }
        return render(request, 'tasks/login.html', context)

def tpslogout(request):
    if request.method == 'POST':
        logout(request)
    return redirect('index')

@login_required
def profile (request):
    return redirect('my_details')


@login_required
def my_details (request):
    u = request.user
    try:
        d: Developer = Developer.objects.get(user=u)
        d = _sanitize_developer_avatar(d)
        avatar_options = _avatar_options()
        allowed_avatar_urls = _avatar_url_set()
        if request.method == 'POST':
            selected_avatar = request.POST.get('avatar_choice', '').strip()
            if selected_avatar in allowed_avatar_urls:
                d.photoURL = selected_avatar
                d.save(update_fields=['photoURL'])

            return render(request, 'tasks/my_details.html', {
                'page_title': 'My Details',
                'dev': d,
                'avatar_options': avatar_options
            })
        else:
            return render(request, 'tasks/my_details.html', {
                'page_title': 'My Details',
                'dev': d,
                'avatar_options': avatar_options
            })
    except ObjectDoesNotExist:
        if request.method == 'POST':
            form = PasswordChangeForm(request.user, data=request.POST)
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, form.user)
                return render(request, 'tasks/password_success.html', {
                    'page_title': 'Password changed.'
                })
            return render(request, 'tasks/profile_lecturer.html', {
                'page_title': 'Account',
                'form': form
            })
        else:
            form = PasswordChangeForm(request.user)
            return render(request, 'tasks/profile_lecturer.html', {
                'page_title': 'Account',
                'form': form
            })

    
@login_required
def change_password(request):
    try:
        d: Developer = Developer.objects.get(user=request.user)
        d = _sanitize_developer_avatar(d)
    except ObjectDoesNotExist:
        d = None

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            return render(request, 'tasks/password_success.html', {
                'page_title': 'Password changed.'
            })
        else:
            return render(
                request,
                'tasks/change_password.html',
                {
                    'page_title': 'Change Password',
                    'form': form,
                    'pass_error': 'Failed. Password not changed.',
                }
            ) 
    else:
        form = PasswordChangeForm(request.user)
        return render(request, 'tasks/change_password.html', {'page_title': 'Change Password', 'form': form, 'dev':d})


@login_required
def my_teams (request):
    try:
        d: Developer = Developer.objects.get(user=request.user)
        d = _sanitize_developer_avatar(d)
    except ObjectDoesNotExist:
        return redirect('my_details')

    teams = d.team.all().order_by('pk')
    allowed_avatar_urls = _avatar_url_set()
    default_avatar_url = _default_avatar_url()
    team_members = dict()
    for team in teams:
        members = list(team.developer_set.all())
        for member in members:
            if member.photoURL not in allowed_avatar_urls:
                member.photoURL = default_avatar_url
        team_members[team] = members

    return render(request, 'tasks/my_teams.html', {
        'page_title': 'My Teams',
        'dev': d,
        'teams': teams,
        'team_members': team_members
    })
 
@login_required
def my_email (request):
    u = request.user
    try:
        d: Developer = Developer.objects.get(user=u)
        d = _sanitize_developer_avatar(d)
    except ObjectDoesNotExist:
        return redirect('my_details')

    if request.method == 'POST':
        form = EmailChangeForm(request.POST, instance=u)
        if form.is_valid():
            form.save()
            return render(request, 'tasks/my_email.html', {
                'page_title': 'Email',
                'user': u,
                'form': form,
                'dev': d
            })
        return render(request, 'tasks/my_email.html', {
            'page_title': 'Email',
            'user': u,
            'form': form,
            'dev': d
        })
    else:
        form = EmailChangeForm(instance = u)
        return render(request, 'tasks/my_email.html', {
            'page_title': 'Email',
            'user': u,
            'form': form,
            'dev': d
        })


@login_required
def my_notifications (request):
    try:
        d: Developer = Developer.objects.get(user=request.user)
        d = _sanitize_developer_avatar(d)
    except ObjectDoesNotExist:
        return redirect('my_details')

    return render(request, 'tasks/my_notifications.html', {
        'page_title': 'Notifications',
        'dev': d
    })

@login_required
@permission_required('tasks.add_mastercourse')
def create_master_course(request):
    mastercourses = MasterCourse.objects.all().order_by('code', 'name')
    mastercourse_error = None

    if request.method == 'POST':
        selected_mastercourse = request.POST.get('mastercourse_choice', '__new__')
        use_new_mastercourse = selected_mastercourse == '__new__'
        form = MasterCourseForm(request.POST)
        form_details = CourseForm(request.POST)
        selected_mastercourse_obj = None
        details_valid = form_details.is_valid()

        if use_new_mastercourse:
            if form.is_valid() and details_valid:
                selected_mastercourse_obj = form.save()
        else:
            try:
                selected_mastercourse_obj = mastercourses.get(pk=int(selected_mastercourse))
            except (TypeError, ValueError, MasterCourse.DoesNotExist):
                mastercourse_error = 'Please select a valid master course.'

        if selected_mastercourse_obj is not None and details_valid:
            course:Course = form_details.save(commit=False)
            course.masterCourse = selected_mastercourse_obj
            course.lecturer = Lecturer.objects.get(user=request.user)
            course.save() 
            return redirect('lecturer_view')
    else: 
        selected_mastercourse = str(mastercourses.first().pk) if mastercourses.exists() else '__new__'
        use_new_mastercourse = selected_mastercourse == '__new__'
        form = MasterCourseForm()
        form_details = CourseForm()
    
    return render(request, 'tasks/course_create.html', {
        'page_title': 'Create New Course',
        'form': form,
        'form_details': form_details,
        'mastercourses': mastercourses,
        'selected_mastercourse': str(selected_mastercourse),
        'use_new_mastercourse': use_new_mastercourse,
        'mastercourse_error': mastercourse_error,
    })

@login_required
@permission_required('tasks.add_team')
@permission_required('tasks.add_developer')
def create_team(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')

    team_assignments = _course_team_assignments(course)
    next_team_no = Team.objects.filter(course=course).count() + 1
    errors = []
    success_message = None

    if request.method == 'POST':
        mode = request.POST.get("mode", "").strip()
        existing_team_names = set(Team.objects.filter(course=course).values_list("name", flat=True))
        default_section = _parse_positive_int(request.POST.get("default_section"), 1)
        default_section_description = (request.POST.get("default_section_description") or "").strip()

        if mode == "manual":
            manual_rows, parse_errors = _parse_manual_team_rows(
                request.POST.get("manual_list", ""),
                default_section,
                default_section_description
            )
            errors.extend(parse_errors)
            if not manual_rows and not errors:
                errors.append("Please provide at least one manual input line.")
            created_teams = 0
            assigned_students = 0
            team_cache = {}

            if not errors:
                for row in manual_rows:
                    team_name = row["team_name"]
                    team = team_cache.get(team_name)
                    if team is None:
                        team = Team.objects.filter(course=course, name=team_name).first()
                        if team is None:
                            team = Team.objects.create(
                                course=course,
                                name=team_name,
                                github=None,
                                supervisor=lecturer
                            )
                            existing_team_names.add(team_name)
                            created_teams += 1
                        team_cache[team_name] = team

                    developer = _get_or_create_student_developer(
                        row["student_id"].strip(),
                        row["first_name"],
                        row["last_name"]
                    )
                    DeveloperCourse.objects.update_or_create(
                        developer=developer,
                        course=course,
                        defaults={
                            "section": row["section"],
                            "description": row["description"],
                        }
                    )

                    already_assigned = developer.team.filter(course=course).exists()
                    if already_assigned:
                        continue
                    developer.team.add(team)
                    assigned_students += 1

                success_message = (
                    f"Manual creation completed. Teams created: {created_teams}. "
                    f"Students assigned: {assigned_students}."
                )

        elif mode == "random":
            random_rows, parse_errors = _parse_random_team_rows(
                request.POST.get("random_list", ""),
                default_section,
                default_section_description
            )
            errors.extend(parse_errors)
            if not random_rows and not errors:
                errors.append("Please provide at least one random input line.")
            team_size = _parse_positive_int(request.POST.get("team_size"), 4)
            pending_developers = []
            seen_student_ids = set()

            if not errors:
                for row in random_rows:
                    student_id = row["student_id"].strip()
                    if student_id in seen_student_ids:
                        continue
                    seen_student_ids.add(student_id)
                    developer = _get_or_create_student_developer(
                        student_id,
                        row["first_name"],
                        row["last_name"]
                    )
                    DeveloperCourse.objects.update_or_create(
                        developer=developer,
                        course=course,
                        defaults={
                            "section": row["section"],
                            "description": row["description"],
                        }
                    )
                    if developer.team.filter(course=course).exists():
                        continue
                    pending_developers.append(developer)

                from random import shuffle
                shuffle(pending_developers)

                group_sizes = _balanced_group_sizes(len(pending_developers), team_size)
                cursor = 0
                created_teams = 0
                for group_size in group_sizes:
                    team_name, next_team_no = _next_default_team_name(existing_team_names, next_team_no)
                    team = Team.objects.create(
                        course=course,
                        name=team_name,
                        github=None,
                        supervisor=lecturer
                    )
                    existing_team_names.add(team_name)
                    created_teams += 1

                    for developer in pending_developers[cursor:cursor + group_size]:
                        developer.team.add(team)
                    cursor += group_size

                success_message = (
                    f"Random generation completed. Teams created: {created_teams}. "
                    f"Students assigned: {len(pending_developers)}."
                )
        else:
            errors.append("Invalid team creation mode.")

        team_assignments = _course_team_assignments(course)

    return render(request, 'tasks/team_create.html', {
        'page_title': 'Create Teams',
        'course': course,
        't_d': team_assignments,
        'errors': errors,
        'success_message': success_message,
    })
            
@login_required
@permission_required('tasks.add_team')
def lecturer_course_view(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')
    milestones = course.milestone_set.all()
    teams = course.team_set.all()
    tasks = list()
    for team in teams:
        for task in team.mastertask_set.all().order_by('pk').reverse():
            tasks.append(task)
    context = {
        'page_title': 'Lecturer Course View',
        'course': course,
        'teams': teams,
        'milestones': milestones,
        'tasks': tasks 
    }

    return render(request, 'tasks/lecturer_course_view.html', context)


@login_required
@permission_required('tasks.add_team')
def end_course(request, course_id):
    if request.method != 'POST':
        return redirect('lecturer_view_course', course_id)
    course = get_object_or_404(Course, pk=course_id)
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')
    if course.active:
        course.active = False
        course.save(update_fields=['active'])
    return redirect('lecturer_view_course', course_id)


@login_required
@permission_required('tasks.add_team')
def lecturer_course_points_view(request, course_id):
    course = get_object_or_404(
        Course.objects.select_related("masterCourse", "lecturer"),
        pk=course_id
    )
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')

    rows, section_rows = _course_section_score_rows(course)

    if request.GET.get("format") == "csv":
        filename = (
            f"course_points_{course.masterCourse.compact_code}_"
            f"{course.academic_year}_{course.semester}.csv"
        ).replace(" ", "")
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow([
            "Section",
            "Section Description",
            "Student ID",
            "Name",
            "Surname",
            "Team",
            "Final Score",
        ])
        for row in rows:
            writer.writerow([
                row["section"] if row["section"] is not None else "",
                row["section_description"],
                row["student_id"],
                row["first_name"],
                row["last_name"],
                row["team_name"],
                row["score"],
            ])
        return response

    context = {
        "page_title": "Course Points",
        "course": course,
        "section_rows": section_rows,
        "total_students": len(rows),
        "total_sections": len(section_rows),
    }
    return render(request, "tasks/course_points_detail.html", context)

@login_required
@permission_required('tasks.add_team')
def lecturer_team_view(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if team.course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')
    points_data = _build_team_points_breakdown(team, current_user=request.user)
    devs = points_data["developers"]
        
    tasks = team.mastertask_set.all().order_by('pk').reverse()
    context = {
        'page_title': 'Lecturer Team View',
        'team': team,
        'course': team.course, 
        'devs': devs, 
        'tasks': tasks,
        'developers' : points_data["developers_summary"]
    }

    return render(request, 'tasks/lecturer_team_view.html', context)


@login_required
@permission_required('tasks.add_team')
def lecturer_team_points_detail(request, team_id):
    team = get_object_or_404(
        Team.objects.select_related("course", "course__masterCourse"),
        pk=team_id
    )
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if team.course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')

    points_data = _build_team_points_breakdown(team, current_user=request.user)
    context = {
        'page_title': 'Team Points Breakdown',
        'team': team,
        'course': team.course,
        'is_lecturer_view': True,
        **points_data
    }
    return render(request, 'tasks/team_points_detail.html', context)


@login_required 
@permission_required('tasks.add_milestone')
def lecturer_create_milestone(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')
    if request.method == 'POST':
        form = MilestoneForm(request.POST)
        if form.is_valid():
            milestone:Milestone = form.save(commit=False)
            milestone.course = course
            milestone.save()
            return redirect('lecturer_view_course', course_id)
    else:
        form = MilestoneForm()
    context = {
        'page_title': 'Create New Milestone',
        'course': course,
        'form': form
    }
    return render(request, "tasks/milestone_create.html", context)

@login_required
@permission_required('tasks.add_milestone')
def lecturer_grade_milestone(request, milestone_id):
    milestone:Milestone = get_object_or_404(Milestone, pk=milestone_id)
    course:Course = milestone.course
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')
    teams = course.team_set.all() 
    if request.method == 'POST':
        for team in teams:
            # print(team.name + '->' + request.POST['grade['+ str(team.pk) +']'])
            q:TeamMilestoneGrade = TeamMilestoneGrade.objects.all().filter(team=team).filter(milestone=milestone)
            if len(q) == 0:
                tp:TeamMilestoneGrade = TeamMilestoneGrade()
                tp.milestone = milestone 
                tp.team = team 
                tp.grade = request.POST['grade[' + str(team.pk) + ']']
                tp.save() 
            else:
                q[0].grade = request.POST['grade[' + str(team.pk) + ']']
                q[0].save()
        return redirect('lecturer_view_course', course.pk)        
    grades = dict()
    for team in teams: 
        q:TeamMilestoneGrade = TeamMilestoneGrade.objects.all().filter(team=team).filter(milestone=milestone)
        if len(q) == 0:
            grades[team.name] = [team.pk, 0]
        else:
            grades[team.name] = [team.pk, q[0].grade]
    context = {
        'page_title': 'Update Grades',
        'milestone': milestone, 
        'course': course, 
        'teams': teams, 
        'grades': grades 
    }
    return render(request, "tasks/milestone_grade.html", context) 

@login_required 
@permission_required('tasks.add_milestone')
def lecturer_edit_milestone(request, milestone_id):
    milestone:Milestone = get_object_or_404(Milestone, pk=milestone_id)
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if milestone.course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')
    if request.method == 'POST':
        form = MilestoneForm(request.POST)
        if form.is_valid():
            mform:Milestone = form.save(commit=False)
            mform.course = milestone.course
            mform.pk = milestone.pk
            mform.save() 
            return redirect('lecturer_view_course', mform.course.pk)
    form = MilestoneForm(instance=milestone)
    context = {
        'page_title': 'Edit Milestone',
        'milestone': milestone,
        'form': form 
    }
    return render(request, "tasks/milestone_edit.html", context)


@login_required
@permission_required('tasks.add_team')
def lecturer_task_view(request, task_id):
    mt:MasterTask = get_object_or_404(MasterTask, pk=task_id)
    t:Task = Task.objects.all().filter(masterTask=mt).order_by('pk').reverse()[0]
    course = mt.team.course
    lecturer = get_object_or_404(Lecturer, user=request.user)
    if course.lecturer_id != lecturer.pk:
        return redirect('lecturer_view')

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment:Comment = form.save(commit=False)
            comment.owner = request.user 
            comment.mastertask = mt 
            comment.task = t 
            comment.save()
            return redirect('lecturer_view_task', task_id)
    form = CommentForm()
    comments = Comment.objects.all().filter(mastertask=mt).order_by('date').reverse()
    v_app = len(Vote.objects.all().filter(task=t).filter(status=mt.status).filter(vote=True))
    v_den = len(Vote.objects.all().filter(task=t).filter(status=mt.status).filter(vote=False))
    if mt.status == 1 and v_app > (len(mt.team.developer_set.all()) - 1) / 2:
        mt.status = 2
        mt.save()
    elif mt.status == 3 and v_app > (len(mt.team.developer_set.all()) - 1) / 2:
        mt.status = 5
        mt.save()

    logs = MasterTaskLog.objects.all().filter(mastertask=mt).order_by('tarih').reverse()

    context = {
        'page_title': 'Lecturer Task View',
        'mastertask': mt,
        'task': t, 
        'tp': mt.difficulty * t.priority,
        'form': form,
        'v_app': v_app,
        'v_den': v_den,
        'comments': comments,
        'course': course, 
        'logs': logs 
    }
    return render(request, "tasks/lecturer_task_view.html", context)

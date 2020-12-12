from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, logout, login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from .models import *
from .forms import *
from .utilities import *
import logging

logger = logging.getLogger('task')


def login_form(request):
    context = {'page_title': 'Login'}
    return render(request, 'tasks/login.html', context)


def leave_site(request):
    logout(request)
    return HttpResponseRedirect('/tasks/')


def tps_login(request):
    oasis_id = request.POST['oasis']
    pwd = request.POST['pass']
    user = authenticate(request, username=oasis_id, password=pwd)
    if user is not None:
        login(request, user)
        return HttpResponseRedirect('/tasks/choose/')
    else:
        context = {
            'page_title': 'Login',
            'login_error': 'Login failed.'
        }
        return render(request, 'tasks/login.html', context)


@login_required
def choose(request):
    if Developer.objects.filter(user=request.user):
        return HttpResponseRedirect('/tasks/team/')
    elif Supervisor.objects.filter(user=request.user):
        return HttpResponseRedirect('/tasks/supervisor/')


@login_required
def supervisor(request):  # this view is for the supervisors only...
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        s = None
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    supervisor_name = s.get_name()
    page_title = "Supervisor page"
    # completed_task_list = request.user.creator.all().filter(status=3).order_by('team', 'due')
    completed_task_list = Task.objects.all().filter(team__supervisor=s, status__range=(3, 4)).order_by('team', 'due')
    supervised_teams = Team.objects.all().filter(supervisor=s)

    context = {
        'page_title': page_title,
        'supervisor_name': supervisor_name,
        'completed_task_list': completed_task_list,
        'supervised_teams': supervised_teams,
    }
    return render(request, 'tasks/supervisor.html', context)


@login_required
def team(request):  # this view is for the developer only...
    d = Developer.objects.get(user=request.user)
    t = d.team
    page_title = t.name + " Team Page"
    developer_name = d.get_name()

    user_task_list = d.assignee.all().filter(status__lt=5).order_by('due')
    team_task_list = t.task_set.all().filter(status__lt=5).order_by('due').exclude(assignee=d)
    teammates = Developer.objects.all().filter(team=t).exclude(id=d.id)

    teammates_task_dict = {}

    for mate in teammates:
        teammates_task_dict.update({mate.get_name(): team_task_list.filter(assignee=mate)})

    context = {
        'page_title': page_title,
        'team_name': t.name,
        'github_url': t.github,
        'current_user': d.id,
        'developer_name': developer_name,
        'user_task_list': user_task_list,
        'team_task_list': team_task_list,
        'teammates_task_dict': teammates_task_dict,
    }
    return render(request, 'tasks/team.html', context)


@login_required
def view_all_teams(request):
    if not request.user.is_superuser:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    context = {
        'page_title': 'All teams and their points',
        'teams': Team.objects.all(),
        'developers': Developer.objects.all(),
        'milestones': Milestone.objects.all(),
    }
    return render(request, 'tasks/view_all_teams.html', context)


# filtering solution https://stackoverflow.com/questions/291945/how-do-i-filter-foreignkey-choices-in-a-django-modelform
@login_required
def supervisor_create(request, team_id):
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        s = None
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    t = get_object_or_404(Team, pk=team_id)
    c = t.course
    m = c.get_current_milestone()
    if request.method == 'POST':
        form = TaskSupervisorForm(t, request.POST)
        if form.is_valid():
            tk = form.save(commit=False)
            tk.creator = request.user
            tk.team = t
            tk.milestone = c.get_current_milestone()
            tk.save()
            return HttpResponseRedirect('/tasks/supervisor/')
    else:
        form = TaskSupervisorForm(t)
    return render(
        request,
        'tasks/supervisor_task_form.html',
        {
            'page_title': 'Create new task',
            'form': form,
            'team_id': t.id,
            'milestone': m
        }
    )


@login_required
def developer_create(request):
    try:
        developer = Developer.objects.get(user=request.user)
    except ObjectDoesNotExist:
        developer = None
        leave_site(request)
        return HttpResponseRedirect('/tasks/')
    dev_team = developer.team
    course = dev_team.course
    milestone = course.get_current_milestone()
    if request.method == 'POST':
        form = TaskDeveloperForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            task.assignee = developer
            task.team = dev_team
            task.milestone = course.get_current_milestone()
            task.save()
            task.apply_self_accept(task.assignee, 1)

            return HttpResponseRedirect('/tasks/team')

    else:
        form = TaskDeveloperForm()

    return render(
        request,
        'tasks/developer_task_form.html',
        {
            'page_title': 'Create new task',
            'form': form,
            'team_id': dev_team.id,
            'milestone': milestone
        }
    )


@login_required
def update(request, task_id, status_id):
    d = None
    if Developer.objects.filter(user=request.user):
        d = Developer.objects.get(user=request.user)

    tsk = get_object_or_404(Task, pk=task_id)
    req_status_id = int(status_id)

    if d is not None:
        if tsk.team != d.team or req_status_id != 3:
            leave_site(request)
            return HttpResponseRedirect('/tasks/')
    if req_status_id > 6 or req_status_id < 1:
        status_id = "5"  # reject it because this is probably a scam...

    if d is not None and status_id == '3':
        tsk.apply_self_accept(d, 3)

    tsk.status = status_id
    tsk.save()
    return HttpResponseRedirect('/tasks/choose/')


@login_required
def update_task_mod(request, task_id, mod):
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        s = None
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    tsk = get_object_or_404(Task, pk=task_id)
    req_mod = int(mod)

    tsk.modifier = req_mod
    tsk.save()
    return HttpResponseRedirect(reverse('tasks:view-task', args=(task_id,)))


@login_required
def view_task(request, task_id):
    tsk = get_object_or_404(Task, pk=task_id)
    priority_color = get_priority_or_difficulty_color(tsk.priority)
    difficulty_color = get_priority_or_difficulty_color(tsk.difficulty)
    can_edit = None
    user_d = None
    user_s = None
    needs_change = False
    if Developer.objects.filter(user=request.user):
        user_d = Developer.objects.get(user=request.user)
        if tsk.assignee == user_d:
            can_edit = 'developer'
        if tsk.team != user_d.team:
            leave_site(request)
            return HttpResponseRedirect('/tasks/')
    elif Supervisor.objects.filter(user=request.user):
        can_edit = 'supervisor'
        user_s = Supervisor.objects.get(user=request.user)

    # THIS PART CAN BE ADDED TO send_vote FUNCTION AND needs_change boolean can be added to Task model
    if user_d:
        if tsk.get_creation_change_votes().count() >= 1:
            needs_change = True

    comment_list = tsk.comment_set.all().order_by("-date")
    vote_list = tsk.vote_set.all()

    form = CommentForm()
    return render(
        request,
        'tasks/view_task.html',
        {
            'page_title': 'View task',
            'task': tsk, 'tid': task_id,
            'comments': comment_list,
            'votes': vote_list,
            'form': form,
            'user_d': user_d,
            'user_s': user_s,
            'can_edit': can_edit,
            'needs_change': needs_change,
            'priority_color': priority_color,
            'difficulty_color': difficulty_color,
        }
    )


@login_required
def send_comment(request, task_id):
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            ct = form.save(commit=False)
            ct.owner = request.user  # Developer.objects.get(user=request.user)
            ct.task = Task.objects.get(pk=task_id)
            ct.save()
            logger.info(request.user.get_username() + ' SENT COMMENT ON TASK ID:' + str(task_id))
    return HttpResponseRedirect('/tasks/' + task_id + '/view/')


# https://docs.djangoproject.com/en/1.8/topics/auth/default/#django.contrib.auth.forms.PasswordChangeForm
@login_required
def change_pass(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            return HttpResponseRedirect('/tasks/choose/')
        else:
            return render(
                request,
                'tasks/change_pass.html',
                {
                    'page_title': 'Change Password',
                    'form': form,
                    'pass_error': 'Password not changed.'
                }
            )
    else:
        form = PasswordChangeForm(request.user)
        return render(
            request,
            'tasks/change_pass.html',
            {
                'page_title': 'Change Password',
                'form': form
            }
        )


@login_required()
def team_all_tasks(request, team_id):
    current_team = get_object_or_404(Team, pk=team_id)
    tasks = current_team.task_set.all().order_by("due")
    return render(
        request,
        'tasks/task_all.html',
        {
            'page_title': 'All tasks for ' + current_team.name,
            'task_list': tasks
        }
    )


@login_required
def task_all(request):
    d = Developer.objects.get(user=request.user)
    t = d.team
    tasks = t.task_set.all().order_by("due")
    return render(
        request,
        'tasks/task_all.html',
        {
            'page_title': 'All tasks',
            'task_list': tasks
        }
    )


@login_required
def team_points(request):
    d = Developer.objects.get(user=request.user)
    t = d.team
    return render(
        request,
        'tasks/team_points.html',
        {
            'page_title': 'Team points',
            'team': t,
            'developers': t.developer_set.all(),
            'milestones': t.course.milestone_set.all()
        })


@login_required
def send_vote(request, task_id, status_id, button_id):
    status_id = int(status_id)
    button_id = int(button_id)
    vote = Vote(voter=request.user, task=Task.objects.get(pk=task_id))
    tsk = get_object_or_404(Task, pk=task_id)

    if status_id == 1 and button_id == 1:
        Vote.objects.all().filter(voter=request.user, task=tsk, vote_type__range=(1, 2)).delete()
        vote.vote_type = 1
    elif status_id == 1 and button_id == 2:
        Vote.objects.all().filter(voter=request.user, task=tsk, vote_type__range=(1, 2)).delete()
        vote.vote_type = 2
    elif status_id == 3 and button_id == 3:
        Vote.objects.all().filter(voter=request.user, task=tsk, vote_type__range=(3, 4)).delete()
        vote.vote_type = 3
    elif status_id == 3 and button_id == 4:
        Vote.objects.all().filter(voter=request.user, task=tsk, vote_type__range=(3, 4)).delete()
        vote.vote_type = 4
    elif status_id == 1 and button_id == 0:
        Vote.objects.all().filter(voter=request.user, task=tsk, vote_type__range=(1, 2)).delete()
    elif status_id == 3 and button_id == 0:
        Vote.objects.all().filter(voter=request.user, task=tsk, vote_type__range=(3, 4)).delete()

    if button_id > 0:
        vote.save()
        tsk.check_for_status_change()
    logger.info(
        request.user.get_username() + " VOTED ON TASK ID: " + str(task_id) + ", VOTE TYPE: " + str(vote.vote_type))
    return HttpResponseRedirect('/tasks/' + task_id + '/view/')


@login_required
def developer_edit_task(request, task_id):
    task_id = int(task_id)
    task_to_edit = Task.objects.get(pk=task_id)
    try:
        developer = Developer.objects.get(user=request.user)
    except ObjectDoesNotExist:
        developer = None
        leave_site(request)
        return HttpResponseRedirect('/tasks/')
    dev_team = developer.team
    course = dev_team.course
    milestone = course.get_current_milestone()
    if request.method == 'POST':
        # instance argument allows existing entry to be edited
        form = TaskDeveloperForm(request.POST, instance=task_to_edit)
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            task.team = dev_team
            Vote.objects.filter(task=task).delete()  # votes are reset here
            task.milestone = course.get_current_milestone()
            task.save()
            task.apply_self_accept(developer, 1)
            return HttpResponseRedirect('/tasks/team')
    else:
        form = TaskDeveloperForm(initial={'title': task_to_edit.title,
                                          'description': task_to_edit.description,
                                          'due': task_to_edit.due,
                                          'priority': task_to_edit.priority,
                                          'difficulty': task_to_edit.difficulty
                                          })
    return render(
        request,
        'tasks/developer_task_form.html',
        {
            'page_title': 'Edit Existing Task',
            'form': form,
            'team_id': dev_team.id,
            'milestone': milestone,
            'is_edit': True,
            'task_id': task_to_edit.id
        }
    )


@login_required
def supervisor_edit_task(request, task_id):
    task_id = int(task_id)
    task_to_edit = Task.objects.get(pk=task_id)
    developer = task_to_edit.assignee

    if Supervisor.objects.get(user=request.user) is None:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    dev_team = developer.team
    course = dev_team.course
    milestone = course.get_current_milestone()
    if request.method == 'POST':
        # instance argument allows existing entry to be edited
        form = TaskSupervisorForm(dev_team, request.POST, instance=task_to_edit)
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            task.team = dev_team
            task.milestone = course.get_current_milestone()

            if task.status == 1:  # if task is in review state reset all votes and remain in current state
                Vote.objects.filter(task=task).delete()  # reset all votes

            task.save()
            return HttpResponseRedirect('/tasks/supervisor/')
    else:
        form = TaskSupervisorForm(dev_team, initial={'assignee': developer,
                                                     'title': task_to_edit.title,
                                                     'description': task_to_edit.description,
                                                     'due': task_to_edit.due,
                                                     'priority': task_to_edit.priority,
                                                     'difficulty': task_to_edit.difficulty
                                                     })
    return render(
        request,
        'tasks/supervisor_task_form.html',
        {
            'page_title': 'Edit Existing Task',
            'form': form,
            'team_id': dev_team.id,
            'milestone': milestone,
            'is_edit': True,
            'task_id': task_to_edit.id
        }
    )


def profile(request):
    return render(
        request,
        'tasks/profile.html',
    )


def teams(request):
    teams_list = Developer.objects.get(user=request.user).team
    return render(
        request,
        'tasks/teams.html',
        {
            'teams_list': teams_list,
        }
    )


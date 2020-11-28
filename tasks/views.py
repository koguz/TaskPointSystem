from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, logout, login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from .models import *
from .forms import *
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
def supervisor(request):    # this view is for the supervisors only...
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        s = None
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    supervisor_name = s.get_name()
    page_title = "Supervisor page"
    completed_task_list = request.user.creator.all().filter(status=3).order_by('team', 'due')
    supervised_teams = Team.objects.all().filter(supervisor=s)

    context = {
        'page_title': page_title,
        'supervisor_name': supervisor_name,
        'completed_task_list': completed_task_list,
        'supervised_teams': supervised_teams,
    }
    return render(request, 'tasks/supervisor.html', context)


@login_required
def team(request):   # this view is for the developer only...
    d = Developer.objects.get(user=request.user)
    t = d.team
    page_title = t.name + " Team Page"
    developer_name = d.get_name()

    user_task_list = d.assignee.all().filter(status__lt=4).order_by('due')
    team_task_list = t.task_set.all().filter(status__lt=4).order_by('due').exclude(assignee=d)

    context = {
        'page_title': page_title,
        'team_name': t.name,
        'github_url': t.github,
        'current_user': d.id,
        'developer_name': developer_name,
        'user_task_list': user_task_list,
        'team_task_list': team_task_list, }
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
        form = TaskDeveloperForm(dev_team, request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            task.team = dev_team
            task.milestone = course.get_current_milestone()
            task.save()
            return HttpResponseRedirect('/tasks/team')
    else:
        form = TaskDeveloperForm(dev_team)
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

    if req_status_id > 5 or req_status_id < 2:
        status_id = "4"  # reject it because this is probably a scam...
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
    can_edit = None
    user_d = None
    user_s = None
    if Developer.objects.filter(user=request.user):
        user_d = Developer.objects.get(user=request.user)
        if tsk.assignee == user_d:
            can_edit = 'developer'
        if tsk.team != user_d.team:
            leave_site(request)
            return HttpResponseRedirect('/tasks/')
    elif Supervisors.objects.filter(user=request.user):
        can_edit = 'supervisor'
        user_s = Supervisor.objects.get(user=request.user)

    comment_list = tsk.comment_set.all().order_by("-date")
    vote_list = tsk.vote_set.all()
    already_voted = tsk.already_voted(request.user)
    form = CommentForm()
    return render(
        request,
        'tasks/view_task.html',
        {
            'page_title': 'View task',
            'task': tsk, 'tid': task_id,
            'comments': comment_list,
            'votes': vote_list,
            'already_voted': already_voted,
            'form': form,
            'user_d': user_d,
            'user_s': user_s,
            'can_edit': can_edit
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
            logger.info(request.user.get_username()+' SENT COMMENT ON TASK ID:'+str(task_id))
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
    # vote.voter = request.user  # Developer.objects.get(user=request.user)
    # vote.task = Task.objects.get(pk=task_id)

    if status_id == 1 and button_id == 1:
        vote.vote_type = 1
    elif status_id == 1 and button_id == 2:
        vote.vote_type = 2
    elif status_id == 3 and button_id == 3:
        vote.vote_type = 3
    elif status_id == 3 and button_id == 4:
        vote.vote_type = 4

    vote.save()
    logger.info(request.user.get_username() + " VOTED ON TASK ID: "+str(task_id) +", VOTE TYPE: "+str(vote.vote_type))
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
        form = TaskDeveloperForm(dev_team, request.POST, instance=task_to_edit) #instance argument allows existing entry to be edited
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            task.team = dev_team
            task.milestone = course.get_current_milestone()
            task.save()
            return HttpResponseRedirect('/tasks/team')
    else:
        form = TaskDeveloperForm(dev_team)
    return render(
        request,
        'tasks/developer_task_form.html',
        {
            'page_title': 'Edit Existing Task',
            'form': form,
            'team_id': dev_team.id,
            'milestone': milestone
        }
    )

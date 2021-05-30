from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.auth import authenticate, logout, login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils.decorators import method_decorator
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import render, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse, reverse_lazy
from .utilities import *
from .models import PointPool
from bootstrap_modal_forms.mixins import PassRequestMixin
from bootstrap_modal_forms.generic import BSModalUpdateView
from .forms import *
from copy import deepcopy
import logging
import os.path
from django.contrib import messages
import random
import math
import json
import unidecode

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
        return HttpResponseRedirect('/tasks/profile/')
    elif Supervisor.objects.filter(user=request.user):
        return HttpResponseRedirect('/tasks/supervisor/')


@login_required
def supervisor(request):  # this view is for the supervisors only...
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    supervisor_name = s.get_name()
    supervisor_photo_url = s.photo_url
    page_title = "Supervisor"
    completed_task_list = Task.objects.all().filter(team__supervisor=s, status__range=(3, 4)).order_by('team', 'due')
    supervised_teams = Team.objects.all().filter(supervisor=s)
    all_teammates = get_all_teammates_of_each_team(supervised_teams, s.user_id)

    context = {
        'page_title': page_title,
        'supervisor_name': supervisor_name,
        'completed_task_list': completed_task_list,
        'supervised_teams': supervised_teams,
        'all_teammates': all_teammates,
        'supervisor_photo_url': supervisor_photo_url,
    }

    return render(request, 'tasks/supervisor.html', context)


@login_required
def supervisor_teams(request):
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    supervisor_name = s.get_name()
    page_title = "Supervised Teams"
    completed_task_list = Task.objects.all().filter(team__supervisor=s, status__range=(3, 4)).order_by('team', 'due')
    supervised_teams = Team.objects.all().filter(supervisor=s)

    context = {
        'page_title': page_title,
        'supervisor_name': supervisor_name,
        'completed_task_list': completed_task_list,
        'supervised_teams': supervised_teams,
    }
    return render(request, 'tasks/supervisor_teams.html', context)


@login_required
def team(request, team_id):  # this view is for the developer only...
    developer = Developer.objects.get(user=request.user)

    try:
        dev_team = Team.objects.get(pk=team_id, developerteam__developer=developer)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/profile/')

    page_title = dev_team.name + " Team Page"
    developer_name = developer.get_name()

    user_task_list = developer.assignee.all().filter(status__lt=5, team=dev_team).order_by('due')
    team_task_list = dev_team.task_set.all().filter(status__lt=5).order_by('due').exclude(assignee=developer)
    teammates = dev_team.get_team_members().exclude(id=developer.id)

    teammates_task_dict = {}

    for mate in teammates:
        teammates_task_dict.update({mate.get_name(): team_task_list.filter(assignee=mate)})

    name_change_count = dev_team.name_change_count
    context = {
        'page_title': page_title,
        'team_name': dev_team.name,
        'name_change_count': name_change_count,
        'team_id': team_id,
        'github_url': dev_team.github,
        'current_user': developer.id,
        'developer_name': developer_name,
        'user_task_list': user_task_list,
        'team_task_list': team_task_list,
        'teammates_task_dict': teammates_task_dict,
    }
    return render(request, 'tasks/team.html', context)


@login_required
def view_all_teams(request):
    if Supervisor.objects.filter(user=request.user).first() is None:
        return HttpResponseRedirect('/tasks/choose')

    context = {
        'page_title': 'All Teams and Their Points',
        'teams': Team.objects.all(),
    }

    return render(request, 'tasks/view_all_teams.html', context)


# filtering solution https://stackoverflow.com/questions/291945/how-do-i-filter-foreignkey-choices-in-a-django-modelform
@login_required
def supervisor_create(request, team_id):
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    dev_team = get_object_or_404(Team, pk=team_id)
    team_name = dev_team.name
    course = dev_team.course
    milestone = course.get_current_milestone()

    if request.method == 'POST':
        form = TaskSupervisorForm(dev_team, request.POST)

        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            task.team = dev_team
            task.milestone = course.get_current_milestone()
            task.save()
            action_record = ActionRecord.task_create(1, s, task)
            TaskDifference.record_task_difference(task, action_record)
            notification_body = request.user.get_full_name() + " acted on task '" + task.title + "': " +action_record.get_action_type_display()
            send_push_notification_to_team(dev_team, notification_body,task, mail=True)

            return HttpResponseRedirect(reverse('tasks:view-task', args=(task.id,)))
    else:
        form = TaskSupervisorForm(dev_team)

    return render(
        request,
        'tasks/supervisor_task_form.html',
        {
            'page_title': 'Create Task For ' + team_name,
            'form': form,
            'team_id': dev_team.id,
            'milestone': milestone,
        }
    )


@login_required
def developer_create(request, team_id):
    try:
        developer = Developer.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    try:
        dev_team = Team.objects.get(pk=team_id, developerteam__developer=developer)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/profile/')

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
            action_record = ActionRecord.task_create(1, developer, task)
            TaskDifference.record_task_difference(task, action_record)
            notification_body = request.user.get_full_name() + " acted on task '" + task.title + "': " + action_record.get_action_type_display()
            send_push_notification_to_team(dev_team, notification_body, request.user, task, mail=True)

            return HttpResponseRedirect(reverse('tasks:view-task', args=(task.id,)))

    else:
        form = TaskDeveloperForm()

    return render(
        request,
        'tasks/developer_task_form.html',
        {
            'page_title': 'Create Task',
            'form': form,
            'team_id': dev_team.id,
            'milestone': milestone
        }
    )


@login_required
def update(request, task_id, status_id):
    developer = None

    if Developer.objects.filter(user=request.user):
        developer = Developer.objects.get(user=request.user)

    task = get_object_or_404(Task, pk=task_id)
    req_status_id = int(status_id)

    if (
        not task.can_be_changed_status_by(request.user) or
        req_status_id > 6 or
        req_status_id < 1 or
        (0 < req_status_id < 3 and not task.half_the_team_accepted() and task.get_submission_change_votes().count() < 1)
    ):
        return HttpResponseRedirect('/tasks/choose/')

    try:
        final_comment = Comment.objects.get(task=task, is_final=True)
    except Comment.DoesNotExist:
        final_comment = None

    if final_comment is not None and task.assignee == developer and status_id == '3' and task.status == 2:
        task.apply_self_accept(developer, 3)
        task.status = status_id
        task.completed_on = datetime.datetime.now()
        task.save()
        action_record = ActionRecord.task_submit(3, developer, task)
    elif task.assignee == developer and status_id == '2' and task.status == 1:
        task.status = status_id
        task.save()
        action_record = ActionRecord.task_status_change_by_developer(7, developer, task)
    elif task.assignee == developer and status_id == '2' and task.status == 3:
        task.status = status_id
        task.unflag_final_comment()
        task.save()
        action_record = ActionRecord.task_status_change_by_developer(7, developer, task)
    elif task.assignee == developer and status_id == '4' and task.status == 3:
        task.status = status_id
        task.save()
        action_record = ActionRecord.task_status_change_by_developer(10, developer, task)
    elif Supervisor.objects.filter(user=request.user).first() is None:
        messages.error(request, 'Task can not be submitted without a final comment.')
        try:
            return redirect(request.META['HTTP_REFERER'])
        except KeyError:
            return HttpResponseRedirect('/tasks/choose/')
    else:
        # TODO: supervisor can change the status no matter what the current status of the task is with urls
        task.status = status_id
        task.save()

        if status_id == '2':
            action_record = ActionRecord.task_approval(6, request.user, task)
        elif status_id == '5':
            action_record = ActionRecord.task_approval(12, request.user, task)
        elif status_id == '6':
            action_record = ActionRecord.task_approval(9, request.user, task)

    notification_body = request.user.get_full_name() + " acted on task '" + task.title + "': " + action_record.get_action_type_display()
    send_push_notification_to_team(task.team, notification_body, request.user,task, mail=True)

    if developer:
        return HttpResponseRedirect(reverse('tasks:view-task', args=(task.id,)))

    return HttpResponseRedirect(reverse('tasks:team-all-tasks', args=(task.team.id, 'due',)))


@login_required
def update_task_mod(request, task_id, mod):
    try:
        Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    task = get_object_or_404(Task, pk=task_id)
    req_mod = int(mod)

    task.modifier = req_mod
    task.save()
    return HttpResponseRedirect(reverse('tasks:view-task', args=(task_id,)))


@login_required
def view_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    priority_color = get_priority_or_difficulty_color(task.priority)
    difficulty_color = get_priority_or_difficulty_color(task.difficulty)
    current_user = request.user
    user_d = Developer.objects.filter(user=current_user).first()
    user_s = Supervisor.objects.filter(user=current_user).first()
    can_edit = None
    creation_needs_change = False
    submission_needs_change = False
    user_can_vote = task.can_be_voted_by(current_user)
    half_the_team_accepted = task.half_the_team_accepted()
    can_change_status = task.can_be_changed_status_by(current_user)
    task_history = task.get_history()

    if not task.team.is_in_team(current_user):
        return HttpResponseRedirect('/tasks/choose/')

    if user_d:
        if task.assignee == user_d:
            can_edit = 'developer'
            submission_needs_change = task.get_submission_change_votes().count() >= 1
            creation_needs_change = task.get_creation_change_votes().count() >= 1
    elif user_s:
        can_edit = 'supervisor'

    comment_list = task.comment_set.all().order_by("-created_on")
    final_comment, all_comments_but_final = check_is_final(comment_list)
    vote_list = task.vote_set.all()
    form = CommentForm()

    return render(
        request,
        'tasks/view_task.html',
        {
            'page_title': 'View Task',
            'task': task,
            'tid': task_id,
            'all_comments_but_final': all_comments_but_final,
            'final_comment': final_comment,
            'votes': vote_list,
            'form': form,
            'user_d': user_d,
            'user_s': user_s,
            'can_edit': can_edit,
            'creation_needs_change': creation_needs_change,
            'submission_needs_change': submission_needs_change,
            'priority_color': priority_color,
            'difficulty_color': difficulty_color,
            'can_vote': user_can_vote,
            'half_the_team_accepted': half_the_team_accepted,
            'can_change_status': can_change_status,
            'task_history': task_history,
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

            if form.cleaned_data['is_final']:
                action_record = ActionRecord.task_comment_final(5, ct.owner, ct.task)
            else:
                action_record = ActionRecord.task_comment(4, ct.owner, ct.task)

            if ct.task.assignee != Developer.objects.filter(user=request.user).first():
                notification_body = request.user.get_full_name() + " acted on task '" + ct.task.title + "': " + action_record.get_action_type_display()
                send_push_notification_to_user(ct.task.assignee.user, notification_body, ct.task, mail=True)
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
def team_all_tasks(request, team_id, order_by="due"):
    current_team = get_object_or_404(Team, pk=team_id)
    task_list = ""

    if order_by == 'due':
        task_list = Task.objects.all().filter(team=current_team).order_by('due')
    elif order_by == 'status':
        task_list = Task.objects.all().filter(team=current_team).order_by("status")
    elif order_by == 'last_modified':
        task_list = Task.objects.all().filter(team=current_team).order_by("-last_modified")
    return render(
        request,
        'tasks/task_all_supervisor.html',
        {
            'page_title': 'All tasks for ' + current_team.name,
            'task_list': task_list,
            'team_id': current_team.id,
            'team_name': current_team.name,
        }
    )


@login_required
def task_all(request, team_id, order_by):
    developer = Developer.objects.get(user=request.user)
    try:
        dev_team = Team.objects.get(pk=team_id, developerteam__developer=developer)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/profile/')

    user_task_list = ""
    task_list = ""

    if order_by == 'due':
        user_task_list = developer.assignee.all().filter(status__lt=5, team=dev_team).order_by('due')
        task_list = Task.objects.all().filter(team=dev_team).exclude(assignee__id=developer.id).order_by('due')
    elif order_by == 'status':
        user_task_list = developer.assignee.all().filter(status__lt=5, team=dev_team).order_by('status')
        task_list = Task.objects.all().filter(team=dev_team).exclude(assignee__id=developer.id).order_by("status")
    elif order_by == 'last_modified':
        user_task_list = developer.assignee.all().filter(status__lt=5, team=dev_team).order_by('-last_modified')
        task_list = Task.objects.all().filter(team=dev_team).exclude(assignee__id=developer.id).order_by("-last_modified")

    return render(
        request,
        'tasks/task_all.html',
        {
            'page_title': 'All tasks',
            'user_task_list': user_task_list,
            'task_list': task_list,
            'team_id': dev_team.id
        }
    )


@login_required
def team_points(request, team_id):
    developer = Developer.objects.get(user=request.user)
    try:
        dev_team = Team.objects.get(pk=team_id, developerteam__developer=developer)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/profile/')

    return render(
        request,
        'tasks/team_points.html',
        {
            'page_title': 'Team Points',
            'team': dev_team,
            'developers': dev_team.get_team_members(),
            'milestones': dev_team.course.milestone_set.all()
        })


@login_required
def send_vote(request, task_id, status_id, button_id):
    developer = Developer.objects.get(user=request.user)
    status_id = int(status_id)
    button_id = int(button_id)
    vote = Vote(voter=developer, task=Task.objects.get(pk=task_id))
    task = get_object_or_404(Task, pk=task_id)
    action_type = 0

    if not task.can_be_voted_by(request.user):
        return HttpResponseRedirect('/tasks/choose/')

    if status_id == 1 and button_id == 1:
        Vote.objects.all().filter(voter=developer, task=task, vote_type__range=(1, 2)).delete()
        vote.vote_type = 1
        action_type = 6
    elif status_id == 1 and button_id == 2:
        Vote.objects.all().filter(voter=developer, task=task, vote_type__range=(1, 2)).delete()
        vote.vote_type = 2
        action_type = 8
    elif status_id == 3 and button_id == 3:
        Vote.objects.all().filter(voter=developer, task=task, vote_type__range=(3, 4)).delete()
        vote.vote_type = 3
        action_type = 9
    elif status_id == 3 and button_id == 4:
        Vote.objects.all().filter(voter=developer, task=task, vote_type__range=(3, 4)).delete()
        vote.vote_type = 4
        action_type = 11

    if 0 <= button_id <= 4 and (status_id == 1 or status_id == 3):
        vote.save()
        task.check_for_status_change()
        action_record = ActionRecord.task_vote(action_type, request.user, task)
        if task.assignee.user != request.user:
            notification_body = request.user.get_full_name() + " acted on task '" + task.title + "': " + action_record.get_action_type_display()
            send_push_notification_to_user(task.assignee.user, notification_body, task, mail=True)
    else:
        return HttpResponseRedirect('/tasks/choose/')

    return HttpResponseRedirect('/tasks/' + task_id + '/view/')


@login_required
def developer_edit_task(request, task_id):
    task_id = int(task_id)
    task_to_edit = Task.objects.get(pk=task_id)

    if task_to_edit.status == 1 and task_to_edit.get_creation_change_votes().count() < 1:
        return HttpResponseRedirect(reverse('tasks:view-task', args=(task_id,)))

    try:
        developer = Developer.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    try:
        dev_team = Team.objects.get(pk=task_to_edit.team.id, developerteam__developer=developer)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/profile/')

    course = dev_team.course
    milestone = course.get_current_milestone()

    if request.method == 'POST':
        # instance argument allows existing entry to be edited
        old_task = deepcopy(task_to_edit)
        form = TaskDeveloperForm(request.POST, instance=task_to_edit)

        if form.is_valid():
            task = form.save(commit=False)
            if task.is_different_from(old_task):
                task.creator = request.user
                task.team = dev_team
                Vote.objects.filter(task=task).delete()  # votes are reset here
                task.milestone = course.get_current_milestone()
                task.save()
                task.apply_self_accept(developer, 1)
                action_record = ActionRecord.task_edit(2, developer, task)
                TaskDifference.record_task_difference(task, action_record)
                notification_body = request.user.get_full_name() + " acted on task '" + task.title + "': " + action_record.get_action_type_display()
                send_push_notification_to_team(dev_team, notification_body, request.user, task, mail=True)

            return HttpResponseRedirect(reverse('tasks:view-task', args=(task_id,)))
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
    dev_team = Team.objects.get(pk=task_to_edit.team.id, developerteam__developer=developer)
    course = dev_team.course
    milestone = course.get_current_milestone()

    if request.method == 'POST':
        # instance argument allows existing entry to be edited
        old_task = deepcopy(task_to_edit)
        form = TaskSupervisorForm(dev_team, request.POST, instance=task_to_edit)

        if form.is_valid():
            task = form.save(commit=False)
            if task.is_different_from(old_task):
                task.creator = request.user
                task.team = dev_team
                task.milestone = course.get_current_milestone()

                if task.status == 1:  # if task is in review state reset all votes and remain in current state
                    Vote.objects.filter(task=task).delete()  # reset all votes
                elif task.status != 2 or task.status != 5 or task.status != 6:
                    task_to_edit.unflag_final_comment()

                task.save()
                action_record = ActionRecord.task_edit(2, Supervisor.objects.get(user=request.user), task)
                TaskDifference.record_task_difference(task, action_record)
                notification_body = request.user.get_full_name() + " acted on task '" + task.title + "': " + action_record.get_action_type_display()
                send_push_notification_to_team(dev_team, notification_body,task, mail=True)

            return HttpResponseRedirect(reverse('tasks:view-task', args=(task_id,)))
    else:
        form = TaskSupervisorForm(
            dev_team,
            initial={
                'assignee': developer,
                'title': task_to_edit.title,
                'description': task_to_edit.description,
                'due': task_to_edit.due,
                'priority': task_to_edit.priority,
                'difficulty': task_to_edit.difficulty
            }
        )
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


@login_required
def profile(request):
    developer = Developer.objects.get(user=request.user)
    developer_photo_url = developer.photo_url
    user_active_tasks = developer.get_active_tasks().order_by('due')
    user_attention_tasks = developer.get_attention_needed_tasks().order_by('due')
    user_all_tasks = developer.get_all_tasks()

    return render(
        request,
        'tasks/profile.html',
        {
            'page_title': 'Profile',
            'user_active_tasks': user_active_tasks,
            'user_attention_tasks': user_attention_tasks,
            'user_all_tasks': user_all_tasks,
            'developer': developer,
            'developer_photo_url': developer_photo_url,
        }
    )


@login_required
def visit_profile(request, developer_id):
    developer = Developer.objects.get(id=developer_id)
    developer_photo = developer.photo_url
    user_task_list = developer.assignee.all().filter(status__lt=5).order_by('due')[:5]

    return render(
        request,
        'tasks/profile.html',
        {
            'page_title': developer.get_name(),
            'user_task_list': user_task_list,
            'developer': developer,
            'developer_photo_url': developer_photo,
        }
    )


@login_required
def teams(request):
    current_developer = Developer.objects.get(user=request.user)
    teams_list = current_developer.get_teams()
    all_teammates = get_all_teammates_of_each_team(teams_list, current_developer.user_id)
    tasks_list = get_all_teams_tasks(teams_list)
    tasks_status_list = get_all_teams_tasks_status(tasks_list, current_developer)

    return render(
        request,
        'tasks/teams.html',
        {
            'page_title': 'Teams',
            'teams': teams_list,
            'all_teammates': all_teammates,
            'tasks_status': tasks_status_list,
        }
    )


@login_required
def notifications(request):
    user_notifications = Notification.objects.filter(user=request.user).order_by('-timestamp')

    for notification in user_notifications:
        notification.is_seen = True
        notification.save()

    return render(
        request,
        'tasks/notifications.html',
        {
            'page_title': 'Notifications',
            'user': request.user,
            'notifications': user_notifications,
        }
    )


@login_required
def calendar(request):
    user_all_tasks = []
    developer = Developer.objects.filter(user=request.user).first()

    if developer:
        user_all_tasks = developer.get_all_tasks()

    return render(
        request,
        'tasks/calendar.html',
        {
            'page_title': 'Calendar',
            'user_all_tasks': user_all_tasks,
        }
    )


@login_required
def sort_active_tasks(request):
    if request.method == 'POST':
        sort_metric = request.POST.get('metric')
        task_list = request.POST.get('tasks')
        sorted_tasks = task_list.order_by(sort_metric)
        # data = serializers.serialize("json", sorted_tasks)
        return JsonResponse({"sorted_tasks": sorted_tasks}, status=200)
    else:
        return JsonResponse({"error": ""}, status=400)


@login_required
def course_data_analytics(request, course_id):
    try:
        Supervisor.objects.get(user=request.user)
        if not os.path.isfile('tasks/static/tasks/gaussian_plots/' + course_id + '/difficult_low_figure.png'):
            calculate_time_diff_and_plot(course_id)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/course_data_analytics.html',
        {
            'page_title': 'Course Data Analytics',
            'course_id': course_id,
        }
    )


@login_required
def data_analytics(request):
    try:
        s = Supervisor.objects.get(user=request.user)
        supervised_courses = Team.objects.values('course', 'course__name', 'course__number_of_students').filter(
            supervisor=s).distinct()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')
    return render(
        request,
        'tasks/data_analytics.html',
        {
            'page_title': 'Data Analytics',
            'courses': supervised_courses,
        }
    )


@login_required
def data_graph_inspect(request, difficulty_and_priority, course_id):
    try:
        Supervisor.objects.get(user=request.user)
        difficulty_and_priority_temp = difficulty_and_priority.split("_")
        difficulty = difficulty_and_priority_temp[0]
        priority = difficulty_and_priority_temp[1]
        task_list = Task.objects.filter(team__course__id=course_id, difficulty=difficulty, priority=priority, status=6)
        average = get_average_completion_time(task_list)
        max, min = get_max_min_completion_time(task_list)
        entry = GraphIntervals.objects.filter(difficulty=difficulty, priority=priority).first()

        if entry is None:
            entry = GraphIntervals(course_id=course_id, difficulty=difficulty, priority=priority)
            entry.save()

        lower_bound = entry.lower_bound
        upper_bound = entry.upper_bound
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')
    return render(
        request,
        'tasks/data_graph_inspect.html',
        {
            'page_title': 'Graph Inspect',
            'difficulty_and_priority': difficulty_and_priority,
            'task_list': task_list,
            'average_completion_time': average,
            'max': max,
            'min': min,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'course_id': course_id,
        }
    )


@login_required
def set_point_pool_interval(request, course_id):
    try:
        Supervisor.objects.get(user=request.user)
        if 'lower_bound' in request.POST and 'upper_bound' in request.POST:
            lower_bound = request.POST['lower_bound']
            upper_bound = request.POST['upper_bound']
            difficulty_and_priority = request.POST['difficulty_and_priority']
            difficulty_and_priority_split = difficulty_and_priority.split("_")
            difficulty = difficulty_and_priority_split[0]
            priority = difficulty_and_priority_split[1]
            try:
                entry = GraphIntervals.objects.get(course=course_id, difficulty=str(difficulty), priority=str(priority))
                if not lower_bound == entry.lower_bound or not upper_bound == entry.upper_bound:
                    entry.upper_bound = upper_bound
                    entry.lower_bound = lower_bound
                entry.save()
            except ObjectDoesNotExist:
                entry = GraphIntervals(course=course_id, difficulty=str(difficulty), priority=str(priority), lower_bound=lower_bound, upper_bound=upper_bound)
                entry.save()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return redirect(request.META['HTTP_REFERER'])


@method_decorator(login_required, name='dispatch')
class TeamRenameView(UserPassesTestMixin, BSModalUpdateView):
    model = Team
    form_class = TeamRenameForm
    pk_url_kwarg = 'team_id'
    template_name = 'form_templates/team_rename_form.html'
    success_message = 'Success: Team Renamed'

    def get_success_url(self):
        return reverse_lazy('tasks:team-home', kwargs={'team_id': self.kwargs['team_id']})

    def test_func(self):
        developer = Developer.objects.get(user=self.request.user)
        team = self.get_object()
        if DeveloperTeam.objects.get(developer=developer, team=team):
            return True
        return False


@login_required
def point_pool(request):
    try:
        supervisor = Supervisor.objects.get(user=request.user)
        course_entry = Course.objects.values().filter(team__supervisor=supervisor)
        course_list = {}
        already_in_course = []
        already_in_team = []
        team_list_with_team_members = {}
        counter = 0
        counter2 = -1
        for index, value in enumerate(course_entry):
            if not value['course'] in already_in_course:
                teams = Team.objects.filter(supervisor=supervisor, course=value['id'])
                for idx, team in enumerate(teams):
                    all_teammates = team.get_team_members()
                    if not (team in already_in_team):
                        team_list_with_team_members.update({counter: {'team': team, 'team_members': all_teammates}})
                        counter += 1
                        already_in_team.append(team)
                counter2 += 1
                course_list.update({counter2: {'id': value['id'], 'course': value['course'], 'course_name': value['name'], 'number_of_students': value['number_of_students'], 'team_weight': value['team_weight'], 'ind_weight': value['ind_weight'], 'teams': team_list_with_team_members}})
                already_in_course.append(value['course'])
                counter = 0
            team_list_with_team_members = {}
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/point_pool.html',
        {
            'page_title': 'Point Pool',
            'course_list': course_list,
        }
    )


@login_required
def calculate_point_pool(request, course_name):
    try:
        s = Supervisor.objects.get(user=request.user)
        courses = Course.objects.filter(course=course_name)
        developers_and_grades = {}
        print(courses)
        if s:
            for course in courses:
                developers_and_grades.update({course: s.calculate_point_pool(course.id)})

        print(developers_and_grades)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/point_pool_course_grade.html',
        {
            'page_title': 'Point Pool Course Grade',
            'developers_and_grades': developers_and_grades,
        }
    )


@login_required
def developer_point_pool_activities(request, course_name, developer_id):
    try:
        Supervisor.objects.get(user=request.user)
        developer = Developer.objects.get(id=developer_id)
        course = Course.objects.get(name=course_name)
        accepted_tasks = Task.objects.filter(team__course__id=course.id, status=6, assignee=developer).order_by('completed_on')
        rejected_tasks = Task.objects.filter(team__course__id=course.id, status=5, assignee=developer).order_by('completed_on')
        comments = Comment.objects.filter(owner=developer.user).order_by('created_on')

        votes = Vote.objects.filter(voter=developer)
        developer_name = developer.get_name()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/developer_point_pool_activities.html',
        {
            'page_title': 'Point Pool Activities',
            'accepted_tasks': accepted_tasks,
            'rejected_tasks': rejected_tasks,
            'developer_name': developer_name,
            'votes': votes,
            'comments': comments,
            'developer': developer,
        }
    )


@login_required
def account_settings(request):
    try:
        if Developer.objects.filter(user=request.user).first():
            user = User.objects.values('first_name', 'last_name', 'email', 'developer__photo_url').get(
                username=request.user)
            user_photo_url = str(user['developer__photo_url'])
        elif Supervisor.objects.filter(user=request.user).first():
            user = User.objects.values('first_name', 'last_name', 'email', 'supervisor__photo_url').get(
                username=request.user)
            user_photo_url = str(user['supervisor__photo_url'])

        user_first_name = str(user['first_name'])
        user_last_name = str(user['last_name'])
        user_email = str(user['email'])

    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/account_settings.html',
        {
            'page_title': 'Account Settings',
            'user_photo_url': user_photo_url,
            'first_name': user_first_name,
            'last_name': user_last_name,
            'email': user_email,
        }

    )


@login_required()
def set_email(request):
    try:
        if 'email' in request.POST:
            print(request.POST['email'])
            user = User.objects.get(username=request.user)
            user.email = request.POST['email']
            user.save()
        if 'photo_url' in request.POST and Developer.objects.filter(user=request.user):
            developer = Developer.objects.get(user=request.user)
            developer.photo_url = request.POST['photo_url']
            developer.save()
        elif 'photo_url' in request.POST and Supervisor.objects.filter(user=request.user):
            supervisor = Supervisor.objects.get(user=request.user)
            supervisor.photo_url = request.POST['photo_url']
            supervisor.save()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return redirect(request.META['HTTP_REFERER'])


@login_required
def courses(request):
    try:
        Supervisor.objects.get(user=request.user)
        course_list = Course.objects.all()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/courses.html',
        {
            'page_title': 'Courses',
            'course_list': course_list,
        }
    )


@login_required
def course(request, course_id):
    try:
        Supervisor.objects.get(user=request.user)
        course_entry = Course.objects.get(id=course_id)
        milestone_list = Milestone.objects.filter(course=course_entry)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/course.html',
        {
            'page_title': course_entry.name,
            'course': course_entry,
            'milestones': milestone_list,
        }
    )


@login_required
def edit_course(request, course_id):
    try:
        Supervisor.objects.get(user=request.user)
        course_entry = Course.objects.get(id=course_id)

        if request.POST['course-name'] and course_entry.name != request.POST['course-name']:
            course_entry.name = request.POST['course-name']
        if request.POST['no-of-students'] and course_entry.number_of_students != request.POST['no-of-students']:
            course_entry.number_of_students = request.POST['no-of-students']
        if request.POST['team-weight'] and course_entry.team_weight != request.POST['team-weight']:
            course_entry.team_weight = request.POST['team-weight']
        if request.POST['individual-weight'] and course_entry.ind_weight != request.POST['individual-weight']:
            course_entry.ind_weight = request.POST['individual-weight']
        course_entry.save()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return redirect(request.META['HTTP_REFERER'])


@login_required
def add_a_course(request):
    try:
        Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/add_a_course.html',
        {
            'page_title': 'Add a Course',
        }
    )


@login_required
def add_the_course(request):
    try:
        Supervisor.objects.get(user=request.user)
        course_entry = Course()
        if request.POST['course'] and course_entry.name != request.POST['course']:
            course_entry.course = request.POST['course']
        if request.POST['no-of-students'] and course_entry.number_of_students != request.POST['no-of-students']:
            course_entry.number_of_students = request.POST['no-of-students']
        if request.POST['team-weight'] and course_entry.team_weight != request.POST['team-weight']:
            course_entry.team_weight = request.POST['team-weight']
        if request.POST['individual-weight'] and course_entry.ind_weight != request.POST['individual-weight']:
            course_entry.ind_weight = request.POST['individual-weight']
        if request.POST['year'] and course_entry.ind_weight != request.POST['year']:
            course_entry.year = request.POST['year']
        if request.POST['term'] and course_entry.ind_weight != request.POST['term']:
            course_entry.term = request.POST['term']
        if request.POST['section'] and course_entry.ind_weight != request.POST['section']:
            course_entry.section = request.POST['section']
        course_entry.save()
        course_entry.create_course_name()
        course_entry.save()

        course_list = Course.objects.all()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/courses.html',
        {
            'page_title': 'Courses',
            'course_list': course_list
        }
    )


@login_required
def add_a_milestone(request, course_id):
    try:
        Supervisor.objects.get(user=request.user)
        course_entry = Course.objects.get(id=course_id)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/add_a_milestone.html',
        {
            'page_title': 'Add a Milestone',
            'course': course_entry,
        }
    )


@login_required
def add_the_milestone(request, course_id):
    try:
        Supervisor.objects.get(user=request.user)
        milestone_entry = Milestone()
        course_entry = Course.objects.get(id=course_id)
        milestone_entry.course = course_entry

        if request.POST['milestone-name']:
            milestone_entry.name = request.POST['milestone-name']
        if request.POST['description']:
            milestone_entry.description = request.POST['description']
        if request.POST['weight']:
            milestone_entry.weight = request.POST['weight']
        if request.POST['due-date']:
            milestone_entry.due = request.POST['due-date']
        milestone_entry.save()

        course_list = Course.objects.all()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/courses.html',
        {
            'page_title': 'Courses',
            'course_list': course_list
        }
    )


@login_required
def milestone(request, course_id, milestone_id):
    try:
        Supervisor.objects.get(user=request.user)
        course_entry = Course.objects.get(id=course_id)
        milestone_entry = Milestone.objects.get(id=milestone_id)
        course_list = Course.objects.all()
        milestone_due = str(milestone_entry.due)
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/milestone.html',
        {
            'page_title': 'Edit Milestone',
            'course': course_entry,
            'milestone': milestone_entry,
            'course_list': course_list,
            'due_date': milestone_due,
        }
    )


@login_required
def edit_milestone(request, course_id, milestone_id):
    try:
        Supervisor.objects.get(user=request.user)
        milestone_entry = Milestone.objects.get(id=milestone_id)
        course_list = Course.objects.all()
        print("Course Name: ", milestone_entry.course)

        if request.POST['course-name']:
            course_entry = Course.objects.get(name=request.POST['course-name'])
            milestone_entry.course = course_entry
        if request.POST['milestone-name']:
            milestone_entry.name = request.POST['milestone-name']
        if request.POST['description']:
            milestone_entry.description = request.POST['description']
        if request.POST['weight']:
            milestone_entry.weight = request.POST['weight']
        if request.POST['due-date']:
            milestone_entry.due = request.POST['due-date']

        milestone_entry.save()
    except ObjectDoesNotExist:
        return HttpResponseRedirect('/tasks/choose/')

    return render(
        request,
        'tasks/courses.html',
        {
            'page_title': 'Courses',
            'course_list': course_list
        }
    )


@login_required()
def course_import(request):
    try:
        supervisor = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
    if request.method == 'POST':
        course = request.read()
        course_data = json.loads(course)
        print(course_data)
        if len(course_data) > 1:
            return HttpResponseRedirect('/tasks/choose/')
        for course_name, teams in course_data.items():
            for team_name, team_members in teams.items():
                team = Team(course=Course.objects.filter(name=course_name).first(), name=team_name, supervisor=supervisor)
                team.save()
                for student_no, student_data in team_members.items():
                    try:
                        developer = Developer.objects.get(id=student_no)
                    except Developer.DoesNotExist:
                        username = (unidecode.unidecode(student_data['first_name']+student_data['last_name']).replace(' ','')).lower()
                        username_salt = ''
                        if username_salt := User.objects.filter(username__icontains=username).count():
                            username = username + str(username_salt)
                        user = User.objects.create_user(
                            username=username,
                            first_name=student_data['first_name'],
                            last_name=student_data['last_name'],
                            password=student_no)
                        user.save()
                        developer = Developer(id=student_no, user=user)
                        developer.save()
                    DeveloperTeam(developer=developer, team=team).save()
                try:
                    DeveloperTeam.objects.filter(team=team)
                except DeveloperTeam.DoesNotExist:
                    team.delete()

        return HttpResponseRedirect('/tasks/choose/')
    else:
        form = CourseImportForm()
    return render(
        request,
        'tasks/course_import.html',
        {
            'page_title': 'Import Students',
            "user": request.user,
            "supervisor": supervisor,
            "form": form,
            "course": 'None',
        }
    )

@login_required()
def import_preview(request):
    try:
        supervisor = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
    form = CourseImportForm(request.POST, request.FILES)
    if request.method == 'POST' and form.is_valid():
        course = form.cleaned_data["course_name"]
        course_name = course.name
        team_size = form.cleaned_data["team_size"]
        course_list_file = form.cleaned_data["course_list_file"]
        students = parse_course_html(course_list_file)
        teams = {}
        num_of_teams = math.ceil(len(students) / team_size)
        teams_from_before = Team.objects.filter(course=course).count()
        for i in range(1, num_of_teams + 1):
            teams['Team-' + str(i+teams_from_before)] = {}
            if not len(students) % team_size:
                students_to_add = team_size
            else:
                students_to_add = team_size - 1
            for j in range(students_to_add):
                student_no, student_values = random.choice(list(students.items()))
                teams['Team-' + str(i+teams_from_before)][student_no] = student_values
                students.pop(student_no)

        course_dict = {str(course_name): teams}
        course_json = json.dumps(course_dict, ensure_ascii=False).encode('utf8')
        return render(
            request,
            'tasks/course_import.html',
            {
                'page_title': 'Import Students',
                "user": request.user,
                "supervisor": supervisor,
                "form": form,
                "course": course_json.decode(),
                "course_dict": course_dict
            }
        )
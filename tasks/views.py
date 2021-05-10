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
from bootstrap_modal_forms.mixins import PassRequestMixin
from bootstrap_modal_forms.generic import BSModalUpdateView
from .forms import TeamRenameForm, CommentForm, TaskSupervisorForm, TaskDeveloperForm
from copy import deepcopy
import logging
from django.contrib import messages

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
    page_title = "Supervisor page"
    completed_task_list = Task.objects.all().filter(team__supervisor=s, status__range=(3, 4)).order_by('team', 'due')
    supervised_teams = Team.objects.all().filter(supervisor=s)

    context = {
        'page_title': page_title,
        'supervisor_name': supervisor_name,
        'completed_task_list': completed_task_list,
        'supervised_teams': supervised_teams,
    }
    return render(request, 'tasks/supervisor.html', context)


def supervisor_teams(request):
    try:
        s = Supervisor.objects.get(user=request.user)
    except ObjectDoesNotExist:
        leave_site(request)
        return HttpResponseRedirect('/tasks/')

    supervisor_name = s.get_name()
    page_title = "Supervisor page"
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

            return HttpResponseRedirect(reverse('tasks:team-all-tasks', args=(team_id, 'due',)))
    else:
        form = TaskSupervisorForm(dev_team)

    return render(
        request,
        'tasks/supervisor_task_form.html',
        {
            'page_title': 'Create new task for ' + team_name,
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

            return HttpResponseRedirect(reverse('tasks:team-home', args=(team_id,)))

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
    developer = None

    if Developer.objects.filter(user=request.user):
        developer = Developer.objects.get(user=request.user)

    task = get_object_or_404(Task, pk=task_id)
    req_status_id = int(status_id)

    if (
        not task.can_be_changed_status_by(request.user) or
        req_status_id > 6 or
        req_status_id < 1 or
        (0 < req_status_id < 3 and not task.half_the_team_accepted() and task.get_submission_change_votes() < 1)
    ):
        return HttpResponseRedirect('/tasks/choose/')

    try:
        final_comment = Comment.objects.get(task=task, is_final=True)
    except Comment.DoesNotExist:
        final_comment = None

    if final_comment is not None and task.assignee == developer and status_id == '3' and task.status == 2:
        task.apply_self_accept(developer, 3)
        task.status = status_id
        task.save()
        ActionRecord.task_submit(3, developer, task)
    elif task.assignee == developer and status_id == '2' and task.status == 1:
        task.status = status_id
        task.save()
        ActionRecord.task_status_change_by_developer(7, developer, task)
    elif task.assignee == developer and status_id == '2' and task.status == 3:
        task.status = status_id
        task.unflag_final_comment()
        task.save()
        ActionRecord.task_status_change_by_developer(7, developer, task)
    elif task.assignee == developer and status_id == '4' and task.status == 3:
        task.status = status_id
        task.save()
        ActionRecord.task_status_change_by_developer(10, developer, task)
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
            ActionRecord.task_approval(6, request.user, task)
        elif status_id == '5':
            ActionRecord.task_approval(12, request.user, task)
        elif status_id == '6':
            ActionRecord.task_approval(9, request.user, task)

    return HttpResponseRedirect('/tasks/choose/')


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
            'page_title': 'View task',
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
                ActionRecord.task_comment_final(5, ct.owner, ct.task)
            else:
                ActionRecord.task_comment(4, ct.owner, ct.task)

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
        task_list = Task.objects.all().filter(team=current_team).order_by("-completed")
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
        user_task_list = developer.assignee.all().filter(status__lt=5, team=dev_team).order_by('-completed')
        task_list = Task.objects.all().filter(team=dev_team).exclude(assignee__id=developer.id).order_by("-completed")

    return render(
        request,
        'tasks/task_all.html',
        {
            'user_task_list': user_task_list,
            'page_title': 'All tasks',
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
            'page_title': 'Team points',
            'team': dev_team,
            'developers': dev_team.get_team_members(),
            'milestones': dev_team.course.milestone_set.all()
        })


@login_required
def send_vote(request, task_id, status_id, button_id):
    status_id = int(status_id)
    button_id = int(button_id)
    vote = Vote(voter=request.user, task=Task.objects.get(pk=task_id))
    task = get_object_or_404(Task, pk=task_id)
    action_type = 0

    if not task.can_be_voted_by(request.user):
        return HttpResponseRedirect('/tasks/choose/')

    if status_id == 1 and button_id == 1:
        Vote.objects.all().filter(voter=request.user, task=task, vote_type__range=(1, 2)).delete()
        vote.vote_type = 1
        action_type = 6
    elif status_id == 1 and button_id == 2:
        Vote.objects.all().filter(voter=request.user, task=task, vote_type__range=(1, 2)).delete()
        vote.vote_type = 2
        action_type = 8
    elif status_id == 3 and button_id == 3:
        Vote.objects.all().filter(voter=request.user, task=task, vote_type__range=(3, 4)).delete()
        vote.vote_type = 3
        action_type = 9
    elif status_id == 3 and button_id == 4:
        Vote.objects.all().filter(voter=request.user, task=task, vote_type__range=(3, 4)).delete()
        vote.vote_type = 4
        action_type = 11

    if 0 <= button_id <= 4 and (status_id == 1 or status_id == 3):
        vote.save()
        task.check_for_status_change()
        ActionRecord.task_vote(action_type, request.user, task)
    else:
        return HttpResponseRedirect('/tasks/choose/')

    return HttpResponseRedirect('/tasks/' + task_id + '/view/')


@login_required
def developer_edit_task(request, task_id):
    task_id = int(task_id)
    task_to_edit = Task.objects.get(pk=task_id)

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
            task.creator = request.user
            task.team = dev_team
            # TODO: votes are reset even if there is no change, we should fix this
            Vote.objects.filter(task=task).delete()  # votes are reset here
            task.milestone = course.get_current_milestone()
            task.save()
            task.apply_self_accept(developer, 1)

            if task.is_different_from(old_task):
                action_record = ActionRecord.task_edit(2, developer, task)
                TaskDifference.record_task_difference(task, action_record)

            return HttpResponseRedirect(reverse('tasks:team-home', args=(task.team.id,)))
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
            task.creator = request.user
            task.team = dev_team
            task.milestone = course.get_current_milestone()

            if task.status == 1:  # if task is in review state reset all votes and remain in current state
                Vote.objects.filter(task=task).delete()  # reset all votes
            elif task.status != 2 or task.status != 5 or task.status != 6:
                task_to_edit.unflag_final_comment()

            task.save()

            if task.is_different_from(old_task):
                action_record = ActionRecord.task_edit(2, Supervisor.objects.get(user=request.user), task)
                TaskDifference.record_task_difference(task, action_record)

            return HttpResponseRedirect(reverse('tasks:team-all-tasks', args=(task.team.id, 'due',)))
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
    developer = Developer.objects.get(user=request.user)
    user_task_list = developer.assignee.all().filter(status__lt=5).order_by('due')[:5]

    return render(
        request,
        'tasks/profile.html',
        {
            'user_task_list': user_task_list,
            'developer': developer,
        }
    )


def visit_profile(request, developer_id):
    developer = Developer.objects.get(id=developer_id)
    user_task_list = developer.assignee.all().filter(status__lt=5).order_by('due')[:5]

    return render(
        request,
        'tasks/profile.html',
        {
            'user_task_list': user_task_list,
            'developer': developer,
        }
    )


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
            'teams': teams_list,
            'all_teammates': all_teammates,
            'tasks_status': tasks_status_list,
        }
    )


def notifications(request):
    return render(
        request,
        'tasks/notifications.html',
        {
            "user": request.user,
        }
    )


def grades(request):
    return render(
        request,
        'tasks/grades.html',
    )


def comments(request):
    return render(
        request,
        'tasks/comments.html',
    )


def calendar(request):
    return render(
        request,
        'tasks/calendar.html',
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

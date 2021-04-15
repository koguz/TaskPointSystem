from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, logout, login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from .models import *


def reset_task_submission_change_votes(task):
    # reset submission change votes if the task is once changed (waiting for rev -> working on it -> waiting for rev)
    Vote.objects.filter(task=task, vote_type=4).delete()


def get_priority_or_difficulty_color(priority_or_difficulty):
    if priority_or_difficulty == 1:
        return "#F3F169"
    elif priority_or_difficulty == 2:
        return "#64F564"
    elif priority_or_difficulty == 3:
        return "#E83535"


def get_all_teammates_of_each_team(teams_list, current_developer_id):
    all_teams_developers = []

    for team in teams_list:
        all_teams_developers.append(
            list(
                team.get_team_members().exclude(user_id=current_developer_id)
            )
        )

    return all_teams_developers


def get_all_teams_tasks(teams_list):
    all_teams_tasks = []

    for team in teams_list:
        all_teams_tasks.append([
            team.get_tasks()
        ])

    return all_teams_tasks


def get_all_teams_tasks_status(tasks_list, current_developer):
    tasks_status_list = []

    for tasks in tasks_list:
        review_tasks = tasks[0].filter(status=1).count()
        working_on_it_tasks = tasks[0].filter(status=2).count()
        waiting_for_review_tasks = tasks[0].filter(status=3).count()
        waiting_for_supervisor_grade_tasks = tasks[0].filter(status=4).count()
        rejected_tasks = tasks[0].filter(status=5).count()
        accepted_tasks = tasks[0].filter(status=6).count()

        tasks_status_dict = {
            'review_tasks': review_tasks,
            'working_on_it_tasks': working_on_it_tasks,
            'waiting_for_review_tasks': waiting_for_review_tasks,
            'waiting_for_supervisor_grade_tasks': waiting_for_supervisor_grade_tasks,
            'rejected_tasks': rejected_tasks,
            'accepted_tasks': accepted_tasks,
            'active_tasks': tasks[0].filter(assignee=current_developer, status__range=(1, 2)).count(),
        }

        tasks_status_list.append(tasks_status_dict)

    return tasks_status_list


def check_is_final(comment_list):
    comments = []
    final_comment = []
    for comment in comment_list:
        if comment.is_final:
            final_comment.append(comment)
        else:
            comments.append(comment)
    return final_comment, comments

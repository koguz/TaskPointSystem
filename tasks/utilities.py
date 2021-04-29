import scipy.stats as stats
import matplotlib.pyplot as plt
import statistics
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, logout, login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from .models import *
import numpy as np


def reset_task_submission_change_votes(task):
    # reset submission change votes if the task is once changed (waiting for rev -> working on it -> waiting for rev)
    Vote.objects.filter(task=task, vote_type__range=(3, 4)).delete()


def get_priority_or_difficulty_color(priority_or_difficulty):
    if priority_or_difficulty == 1:
        return "#F3F169"
    elif priority_or_difficulty == 2:
        return "#64F564"
    elif priority_or_difficulty == 3:
        return "#E83535"


def get_all_teammates_of_each_team(teams_list, current_user_id):
    all_teams_developers = []
    try:
        s = Supervisor.objects.get(user_id=current_user_id)
        for team in teams_list:
            all_teams_developers.append(
                list(
                    team.get_team_members()
                )
            )
    except ObjectDoesNotExist:
        for team in teams_list:
            all_teams_developers.append(
                list(
                    team.get_team_members().exclude(user_id=current_user_id)
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


def get_all_task_time_diff():

    easy_low_list_time_diff = np.array([])
    easy_planned_list_time_diff = np.array([])
    easy_urgent_list_time_diff = np.array([])
    normal_low_list_time_diff = np.array([])
    normal_planned_list_time_diff = np.array([])
    normal_urgent_list_time_diff = np.array([])
    difficult_low_list_time_diff = np.array([])
    difficult_planned_list_time_diff = np.array([])
    difficult_urgent_list_time_diff = np.array([])

    easy_low_list = Task.objects.filter(priority=1, difficulty=1, status=6)
    easy_planned_list = Task.objects.filter(priority=2, difficulty=1, status=6)
    easy_urgent_list = Task.objects.filter(priority=3, difficulty=1, status=6)

    normal_low_list = Task.objects.filter(priority=1, difficulty=2, status=6)
    normal_planned_list = Task.objects.filter(priority=2, difficulty=2, status=6)
    normal_urgent_list = Task.objects.filter(priority=3, difficulty=2, status=6)

    difficult_low_list = Task.objects.filter(priority=1, difficulty=3, status=6)
    difficult_planned_list = Task.objects.filter(priority=2, difficulty=3, status=6)
    difficult_urgent_list = Task.objects.filter(priority=3, difficulty=3, status=6)

    for task in easy_low_list:
        easy_low_list_time_diff = np.append(easy_low_list_time_diff, ((task.completed_on-task.created_on).total_seconds())/3600)

    for task in easy_planned_list:
        easy_planned_list_time_diff = np.append(easy_planned_list_time_diff, ((task.completed_on-task.created_on).total_seconds())/3600)

    for task in easy_urgent_list:
        easy_urgent_list_time_diff = np.append(easy_urgent_list_time_diff, ((task.completed_on-task.created_on).total_seconds())/3600)

    for task in normal_low_list:
        normal_low_list_time_diff = np.append(normal_low_list_time_diff, ((task.completed_on-task.created_on).total_seconds())/3600)

    for task in normal_planned_list:
        normal_planned_list_time_diff = np.append(normal_planned_list_time_diff, ((task.completed_on - task.created_on).total_seconds())/3600)

    for task in normal_urgent_list:
        normal_urgent_list_time_diff = np.append(normal_urgent_list_time_diff, ((task.completed_on - task.created_on).total_seconds())/3600)

    for task in difficult_low_list:
        difficult_low_list_time_diff = np.append(difficult_low_list_time_diff, ((task.completed_on - task.created_on).total_seconds())/3600)

    for task in difficult_planned_list:
        difficult_planned_list_time_diff = np.append(difficult_planned_list_time_diff,
                                                     ((task.completed_on - task.created_on).total_seconds())/3600)

    for task in difficult_urgent_list:
        difficult_urgent_list_time_diff = np.append(difficult_urgent_list_time_diff,
                                                    ((task.completed_on - task.created_on).total_seconds())/3600)

    plot_gaussian(easy_low_list_time_diff, 'easy_low')
    plot_gaussian(easy_planned_list_time_diff, 'easy_planned')
    plot_gaussian(easy_urgent_list_time_diff, 'easy_urgent')
    plot_gaussian(normal_low_list_time_diff, 'normal_low')
    plot_gaussian(normal_planned_list_time_diff, 'normal_planned')
    plot_gaussian(normal_urgent_list_time_diff, 'normal_urgent')
    plot_gaussian(difficult_low_list_time_diff, 'difficult_low')
    plot_gaussian(difficult_planned_list_time_diff, 'difficult_planned')
    plot_gaussian(difficult_urgent_list_time_diff, 'difficult_urgent')


def plot_gaussian(time_diff_list, title):

    time_diff_list = np.sort(time_diff_list)

    mean = statistics.mean(time_diff_list)
    standard_deviation = statistics.stdev(time_diff_list)

    x_values = np.arange((time_diff_list[0]-10), (time_diff_list[len(time_diff_list)-1]+10), 1)
    # x_values = np.arange(20, 100, 0.001)
    y_values = stats.norm.pdf(x_values, mean, standard_deviation)
    plt.plot(x_values, y_values)
    plt.title(title)
    plt.savefig('tasks/static/tasks/' + title + '_figure.png')
    plt.close()
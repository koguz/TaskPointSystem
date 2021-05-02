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
import math


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


def calculate_time_diff_and_plot():
    time_diff_list = np.array([])

    for difficulty in range(1, 4):
        for priority in range(1, 4):
            task_list = Task.objects.filter(priority=priority, difficulty=difficulty, status=6)
            for task in task_list:
                time_diff_list = np.append(time_diff_list,
                                           ((task.completed_on - task.created_on).total_seconds()) / 3600)
            difficulty_and_priority = str(difficulty) + "_" + str(priority)
            plot_gaussian(time_diff_list, difficulty_and_priority)


def plot_gaussian(time_diff_list, difficulty_and_priority):
    time_diff_list = np.sort(time_diff_list)

    mean = statistics.mean(time_diff_list)
    standard_deviation = statistics.stdev(time_diff_list)

    x_values = np.arange((time_diff_list[0]), (time_diff_list[len(time_diff_list) - 1]), 1)
    y_values = stats.norm.pdf(x_values, mean, standard_deviation)
    plt.plot(x_values, y_values)

    if difficulty_and_priority == "1_1":
        title = "easy_low"
    elif difficulty_and_priority == "1_2":
        title = "easy_planned"
    elif difficulty_and_priority == "1_3":
        title = "easy_urgent"
    elif difficulty_and_priority == "2_1":
        title = "normal_low"
    elif difficulty_and_priority == "2_2":
        title = "normal_planned"
    elif difficulty_and_priority == "2_3":
        title = "normal_urgent"
    elif difficulty_and_priority == "3_1":
        title = "difficult_low"
    elif difficulty_and_priority == "3_2":
        title = "difficult_planned"
    elif difficulty_and_priority == "3_3":
        title = "difficult_urgent"
    else:
        title = "invalid difficulty and priority"

    plt.title(title)
    plt.savefig('tasks/static/tasks/gaussian_plots' + title + '_figure.png')
    plt.close()


def get_average_completion_time(task_list):
    total_time = 0
    counter = 0

    for task in task_list:
        total_time += ((task.completed_on - task.created_on).total_seconds()/3600)
        counter += 1

    return math.floor(total_time/counter)


def get_max_min_completion_time(task_list):
    time_diff = np.array([])

    for task in task_list:
        time_diff = np.append(time_diff, ((task.completed_on - task.created_on).total_seconds() / 3600))

    return math.floor(max(time_diff)), math.floor(min(time_diff))

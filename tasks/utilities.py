from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, logout, login, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from .models import *
from webpush import send_user_notification
from webpush.utils import send_to_subscription
from django.core.mail import send_mail
import numpy as np
import math
import os.path
import scipy.stats as stats
import matplotlib.pyplot as plt
import statistics
from html.parser import HTMLParser
import codecs


def reset_task_submission_change_votes(task):
    # reset submission change votes if the task is once changed (waiting for rev -> working on it -> waiting for rev)
    Vote.objects.filter(task=task, vote_type__range=(3, 4)).delete()


def get_priority_or_difficulty_color(priority_or_difficulty):
    if priority_or_difficulty == 1:
        return "#FFC107"
    elif priority_or_difficulty == 2:
        return "#28A745"
    elif priority_or_difficulty == 3:
        return "#DC3545"


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


def send_push_notification_to_user(user, description, task=None, mail=False):
    payload = {"head": "TPS Notification!", "body": description}
    send_user_notification(user=user, payload=payload, ttl=1000)
    if task:
        Notification(user= user, body=description, related_task=task).save()
    if mail:
        email_body = "Hello " +user.get_full_name()+",\n" + description
        send_mail(
            'TPS Nofitication',
            email_body,
            'tpsdeneme@gmail.com',
            [user.email],
            fail_silently=False,
        )


def send_push_notification_to_team(team, description, excluded_user=None, task=None, mail=False):
    payload = {"head": "TPS Notification!", "body": description}
    developers = [developer_team.developer for developer_team in DeveloperTeam.objects.filter(team=team)]
    users = [developer.user for developer in developers]

    if excluded_user and excluded_user in users:
        users.remove(excluded_user)

    for user in users:
        send_user_notification(user=user, payload=payload, ttl=1000)
        Notification(user=user, body=description, related_task=task).save()
        if mail:
            email_body = "Hello " + user.get_full_name() + ",\n" + description
            send_mail(
                'TPS Nofitication',
                email_body,
                'tpsdeneme@gmail.com',
                [user.email],
                fail_silently=False,
            )


def calculate_time_diff_and_plot(course_id):
    time_diff_list = np.array([])

    for difficulty in range(1, 4):
        for priority in range(1, 4):
            task_list = Task.objects.filter(team__course__id=course_id, priority=priority, difficulty=difficulty, status=6)
            for task in task_list:
                time_diff_list = np.append(time_diff_list,
                                           ((task.completed_on - task.created_on).total_seconds()) / 3600)
            difficulty_and_priority = str(difficulty) + "_" + str(priority)
            plot_gaussian(time_diff_list, difficulty_and_priority, course_id)


def plot_gaussian(time_diff_list, difficulty_and_priority, course_id):
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
    if not os.path.isdir('tasks/static/tasks/gaussian_plots/' + course_id):
        os.mkdir('tasks/static/tasks/gaussian_plots/' + course_id)
    plt.savefig('tasks/static/tasks/gaussian_plots/' + course_id + '/' + title + '_figure.png')
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


def parse_course_html(course_file):
    class MyHTMLParser(HTMLParser):

        def handle_starttag(self, tag, attrs):
            if attrs == [('class', 'align-middle')] or attrs == [('class', 'align-middle print-fs-8')] and tag == 'td':
                self.start_tag_count += 1
            elif attrs == [('class', 'align-middle text-center font-weight-bold')]:
                self.start_tag_count = 0

        def handle_data(self, data):
            if 0 < self.start_tag_count < 4 and data.strip() != '':
                if self.start_tag_count == 1:
                    self.current_student = data
                    self.dict[self.current_student] = {}
                elif self.start_tag_count == 2:
                    self.dict[self.current_student]['first_name'] = data
                elif self.start_tag_count == 3:
                    self.dict[self.current_student]['last_name'] = data

        def __init__(self, dict):
            self.start_tag_count = 10
            self.dict = dict
            self.current_student = ''
            HTMLParser.__init__(self)

    file = codecs.EncodedFile(course_file,"utf-8")
    students = {}
    parser = MyHTMLParser(students)
    parser.feed(file.read().decode("utf-8"))
    return students
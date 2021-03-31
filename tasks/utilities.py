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


def get_all_teams_of_developer(developer_id):
    developer_team_ids = DeveloperTeam.objects.all().filter(developer__user_id=developer_id)
    developer_teams = []

    for developer_team in developer_team_ids:
        team = Team.objects.all().filter(pk=developer_team.team_id)
        developer_teams.append(team)

    return developer_teams


def get_all_teammates_of_each_team(teams_list, current_developer_id):
    all_teams_developers = []

    for team in teams_list:
        team_id = team[0].id
        developer_ids = DeveloperTeam.objects.all().filter(team_id=team_id)
        team_developers = []

        for developer_team_object in developer_ids:
            developer_id = developer_team_object.developer_id
            developer = Developer.objects.all().get(pk=developer_id)
            team_developers.append(developer)

        all_teams_developers.append(team_developers)

    return all_teams_developers

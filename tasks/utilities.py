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


def reset_task_submission_votes(task):
    # reset submission votes if the task is revived
    if task.status == 5:
        Vote.objects.filter(task=task, vote_type__range=(3, 4)).delete()


def reset_task_submission_change_votes(task):
    # reset submission change votes if the task is once changed (waiting for rev -> working on it -> waiting for rev)
    Vote.objects.filter(task=task, vote_type=4).delete()


def get_priority_or_difficulty_color(priority_or_difficulty):
    if priority_or_difficulty == 1:
        return "yellow"
    elif priority_or_difficulty == 2:
        return "green"
    elif priority_or_difficulty == 3:
        return "red"


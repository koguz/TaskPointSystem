# Generated by Django 3.0.3 on 2020-11-28 01:23

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import tasks.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256, verbose_name='Course Name')),
                ('number_of_students', models.PositiveSmallIntegerField(default=40, validators=[django.core.validators.MaxValueValidator(99), django.core.validators.MinValueValidator(1)], verbose_name='Number of Students')),
                ('team_weight', models.PositiveSmallIntegerField(default=40, validators=[django.core.validators.MaxValueValidator(99), django.core.validators.MinValueValidator(1)], verbose_name='Team weight')),
                ('ind_weight', models.PositiveSmallIntegerField(default=60, validators=[django.core.validators.MaxValueValidator(99), django.core.validators.MinValueValidator(1)], verbose_name='Individual weight')),
            ],
        ),
        migrations.CreateModel(
            name='Developer',
            fields=[
                ('id', models.CharField(max_length=12, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='Milestone',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='Milestone')),
                ('description', models.TextField(verbose_name='Milestone details')),
                ('weight', models.PositiveSmallIntegerField(default=10, validators=[django.core.validators.MaxValueValidator(100), django.core.validators.MinValueValidator(1)], verbose_name='Weight')),
                ('due', models.DateField(verbose_name='Due Date')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.Course')),
            ],
        ),
        migrations.CreateModel(
            name='Supervisor',
            fields=[
                ('id', models.CharField(max_length=12, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=256, verbose_name='Brief task name')),
                ('description', models.TextField(verbose_name='Description')),
                ('due', models.DateField(validators=[tasks.models.past_date_validator], verbose_name='Due Date')),
                ('date', models.DateTimeField(auto_now_add=True, verbose_name='Created on')),
                ('completed', models.DateTimeField(auto_now=True, null=True, verbose_name='Completed on')),
                ('priority', models.PositiveSmallIntegerField(choices=[(3, 'Urgent'), (2, 'Planned'), (1, 'Low')], default=2, verbose_name='Priority')),
                ('difficulty', models.PositiveSmallIntegerField(choices=[(3, 'Difficult'), (2, 'Normal'), (1, 'Easy')], default=2, verbose_name='Difficulty')),
                ('modifier', models.PositiveSmallIntegerField(default=3, validators=[django.core.validators.MaxValueValidator(5), django.core.validators.MinValueValidator(1)], verbose_name='Modifier')),
                ('status', models.PositiveSmallIntegerField(choices=[(1, 'Review'), (2, 'Working on it'), (3, 'Waiting for review'), (4, 'Waiting for supervisor grade'), (5, 'Rejected'), (6, 'Accepted')], default=1, verbose_name='Status')),
                ('valid', models.BooleanField(default=False, verbose_name='Is Valid')),
                ('assignee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignee', to='tasks.Developer', verbose_name='Assigned to')),
                ('creator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('milestone', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.Milestone')),
            ],
        ),
        migrations.CreateModel(
            name='Vote',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vote_type', models.PositiveSmallIntegerField(choices=[(1, 'Task Creation Accepted'), (2, 'Task Creation Rejected'), (3, 'Task Submission Accepted'), (4, 'Task Submission Rejected')], default=1, verbose_name='Vote Type')),
                ('date', models.DateTimeField(auto_now_add=True, verbose_name='Date')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='tasks.Task')),
                ('voter', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='Team Name')),
                ('github', models.CharField(max_length=256, null=True, verbose_name='Git Page')),
                ('team_size', models.PositiveSmallIntegerField(default=4, validators=[django.core.validators.MaxValueValidator(99), django.core.validators.MinValueValidator(1)], verbose_name='Team size')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.Course')),
                ('supervisor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tasks.Supervisor')),
            ],
        ),
        migrations.AddField(
            model_name='task',
            name='team',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.Team'),
        ),
        migrations.AddField(
            model_name='developer',
            name='team',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tasks.Team'),
        ),
        migrations.AddField(
            model_name='developer',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(verbose_name='Comment')),
                ('file_url', models.URLField(blank=True, max_length=512, null=True, verbose_name='File URL')),
                ('date', models.DateTimeField(auto_now_add=True, verbose_name='Date')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.Task')),
            ],
        ),
    ]

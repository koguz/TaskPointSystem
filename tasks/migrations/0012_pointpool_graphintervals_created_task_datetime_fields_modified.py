# Generated by Django 3.1.4 on 2021-05-22 16:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tasks', '0011_added_action_record_and_task_difference_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='task',
            name='completed',
        ),
        migrations.RemoveField(
            model_name='task',
            name='valid',
        ),
        migrations.AddField(
            model_name='task',
            name='completed_on',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Completed on'),
        ),
        migrations.AddField(
            model_name='task',
            name='created_on',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Created on'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='task',
            name='creation_approved_on',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Creation approved on'),
        ),
        migrations.AddField(
            model_name='task',
            name='submission_approved_on',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Submission approved on'),
        ),
        migrations.AlterField(
            model_name='actionrecord',
            name='actor',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='actionrecord',
            name='object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.task'),
        ),
        migrations.AlterField(
            model_name='task',
            name='title',
            field=models.CharField(max_length=256, verbose_name='Task title'),
        ),
        migrations.AlterField(
            model_name='taskdifference',
            name='action_record',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.actionrecord'),
        ),
        migrations.AlterField(
            model_name='taskdifference',
            name='assignee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.developer'),
        ),
        migrations.AlterField(
            model_name='taskdifference',
            name='task',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.task'),
        ),
        migrations.AlterField(
            model_name='vote',
            name='voter',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.developer'),
        ),
        migrations.CreateModel(
            name='PointPool',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('point', models.PositiveIntegerField(default=0)),
                ('course', models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='tasks.course')),
                ('developer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.developer')),
            ],
        ),
        migrations.CreateModel(
            name='GraphIntervals',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('difficulty', models.SmallIntegerField(default=0, verbose_name='Difficulty')),
                ('priority', models.SmallIntegerField(default=0, verbose_name='Priority')),
                ('lower_bound', models.IntegerField(default=-1, verbose_name='Lower Bound')),
                ('upper_bound', models.IntegerField(default=-1, verbose_name='Upper Bound')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.course')),
            ],
        ),
        migrations.AddConstraint(
            model_name='graphintervals',
            constraint=models.UniqueConstraint(fields=('difficulty', 'priority'), name='name of constraint'),
        ),
    ]
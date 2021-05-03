# Generated by Django 3.1.4 on 2021-05-03 17:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0013_pointpool_course'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphIntervals',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('difficulty', models.SmallIntegerField(default=0, verbose_name='Difficulty')),
                ('priority', models.SmallIntegerField(default=0, verbose_name='Priority')),
                ('lower_bound', models.IntegerField(default=-1, verbose_name='Lower Bound')),
                ('upper_bound', models.IntegerField(default=-1, verbose_name='Upper Bound')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tasks.task')),
            ],
        ),
    ]

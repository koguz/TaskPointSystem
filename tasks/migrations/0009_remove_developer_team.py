# Generated by Django 3.1.7 on 2021-04-03 22:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0008_merge_00005-0007'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='developer',
            name='team',
        ),
    ]

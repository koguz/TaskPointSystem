# Generated by Django 3.1.4 on 2021-04-01 19:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0008_merge_20210331_2252'),
    ]

    operations = [
        migrations.RenameField(
            model_name='comment',
            old_name='isfinal',
            new_name='is_final',
        ),
    ]
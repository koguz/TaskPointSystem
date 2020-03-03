from django.contrib import admin
from .models import Course, Milestone, Team, Task, Developer, Comment, Supervisor, Vote

# Register your models here.

admin.site.register(Course)
admin.site.register(Milestone)
admin.site.register(Team)
admin.site.register(Task)
admin.site.register(Developer)
admin.site.register(Comment)
admin.site.register(Supervisor)
admin.site.register(Vote)

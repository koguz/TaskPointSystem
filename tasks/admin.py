from django.contrib import admin
from .models import * 

# Register your models here.

admin.site.register(Lecturer)
admin.site.register(Developer)
admin.site.register(MasterCourse)
admin.site.register(Course)
admin.site.register(Milestone)
admin.site.register(Team)
admin.site.register(MasterTask)
admin.site.register(Task)
admin.site.register(Comment)
admin.site.register(Vote)
admin.site.register(Like)
admin.site.register(MasterTaskLog)
admin.site.register(TeamMilestoneGrade)

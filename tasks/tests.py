import datetime

from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import \
    Course,\
    Milestone,\
    Team,\
    Task,\
    Developer,\
    Comment,\
    Supervisor,\
    Vote,\
    User,\
    DeveloperTeam,\
    past_date_validator


class TaskModelTests(TestCase):
    def setUp(self):
        user_one = User.objects.create(id=1, username='user_one', first_name='Developer', last_name='One')
        user_two = User.objects.create(id=2, username='user_two', first_name='Developer', last_name='Two')
        user_three = User.objects.create(id=3, username='user_three', first_name='Developer', last_name='Three')
        user_four = User.objects.create(id=4, username='user_four', first_name='Supervisor', last_name='One')
        user_five = User.objects.create(id=5, username='user_five', first_name='Supervisor', last_name='Two')
        user_six = User.objects.create(id=6, username='user_six', first_name='Developer', last_name='Four')
        developer_one = Developer.objects.create(id=1, user=user_one)
        developer_two = Developer.objects.create(id=2, user=user_two)
        Developer.objects.create(id=3, user=user_three)
        developer_four = Developer.objects.create(id=4, user=user_six)
        supervisor_one = Supervisor.objects.create(id=1, user=user_four)
        Supervisor.objects.create(id=2, user=user_five)
        course_one = Course.objects.create(name='Course 1 Name', course='Course 1 Course', section=1, year=2020, term=1)
        milestone_one = Milestone.objects.create(
            name='Milestone 1',
            course=course_one,
            description='Milestone 1 description',
            due=timezone.now() + datetime.timedelta(days=20),
        )
        team_one = Team.objects.create(name='Team 1', course=course_one, supervisor=supervisor_one, team_size=3)
        task_one = Task.objects.create(
            id=1,
            title='Test task 1',
            description='Test task 1 description',
            assignee=developer_one,
            difficulty=2,
            priority=2,
            modifier=3,
            due=timezone.now() + datetime.timedelta(days=10),
            milestone=milestone_one,
            team=team_one,
        )
        Task.objects.create(
            id=2,
            title='Test task 2',
            description='Test task 2 description',
            assignee=developer_two,
            difficulty=2,
            priority=2,
            modifier=3,
            due=timezone.now() + datetime.timedelta(days=10),
            milestone=milestone_one,
            team=team_one,
        )
        task_three = Task.objects.create(
            id=3,
            title='Test task 3',
            description='Test task 3 description',
            assignee=developer_two,
            difficulty=1,
            priority=3,
            modifier=5,
            due=timezone.now() + datetime.timedelta(days=10),
            milestone=milestone_one,
            team=team_one,
        )
        Comment.objects.create(id=1, owner=user_one, task=task_one, body='Comment one', is_final=True)
        Comment.objects.create(id=2, owner=user_one, task=task_one, body='Comment two', is_final=False)
        DeveloperTeam.objects.create(id=1, developer=developer_one, team=team_one)
        DeveloperTeam.objects.create(id=2, developer=developer_two, team=team_one)
        DeveloperTeam.objects.create(id=3, developer=developer_four, team=team_one)
        Vote.objects.create(id=1, voter=developer_one, task=task_one, vote_type=1)
        Vote.objects.create(id=2, voter=developer_four, task=task_one, vote_type=2)
        Vote.objects.create(id=3, voter=developer_one, task=task_one, vote_type=3)
        Vote.objects.create(id=4, voter=developer_four, task=task_one, vote_type=4)
        Vote.objects.create(id=5, voter=developer_one, task=task_three, vote_type=1)
        Vote.objects.create(id=6, voter=developer_two, task=task_three, vote_type=1)

    def test_past_date_validator_past(self):
        past_date = timezone.now() - datetime.timedelta(days=1)
        past_date = past_date.date()
        Task(due=past_date)

        self.assertRaises(ValidationError)

    def test_past_date_validator_not_past(self):
        past_date = timezone.now() + datetime.timedelta(days=1)
        past_date = past_date.date()
        task = Task(due=past_date)

        self.assertEqual(past_date_validator(task.due), None)

    def test_task_title_length_pass(self):
        task = Task(title='This is a title which has less than 51 characters')

        self.assertLessEqual(len(task.title), 50, 'Task title should be less than 51 characters')

    def test_task_title_length_fail(self):
        task = Task(title='This is a title which has more than fifty characters')

        self.assertGreater(len(task.title), 50, 'Task title should be greater than 50 characters')

    def test_task_description_length_pass(self):
        task = Task(description='This is a description which has less than 256 characters')

        self.assertLessEqual(len(task.description), 256, 'Task description should be less than 257 characters')

    def test_task_description_length_fail(self):
        task = Task(description='This is a description which has more than 256 characters. Lorem ipsum dolor sit '
                                'amet, consectetur adipiscing elit. Cras varius nisl non bibendum scelerisque. '
                                'Pellentesque ultricies maximus imperdiet. Suspendisse vel pulvinar neque. Nullam eu '
                                'dolor a lacus malesuada lacinia.')

        self.assertGreater(len(task.description), 256, 'Task description should be greater than 256 characters')

    def test_task_get_points_pass(self):
        task_one = Task(difficulty=2, priority=2, modifier=4)
        actual_task_point_one = (task_one.difficulty * task_one.priority) + task_one.modifier

        task_two = Task(difficulty=3, priority=2, modifier=5)
        actual_task_point_two = 11

        with self.subTest():
            self.assertEqual(task_one.get_points(), actual_task_point_one,
                             'Task point should be ' + str(actual_task_point_one))

        with self.subTest():
            self.assertEqual(task_two.get_points(), actual_task_point_two,
                             'Task point should be ' + str(actual_task_point_two))

    def test_task_get_points_fail(self):
        task = Task(difficulty=1, priority=2, modifier=2)
        false_task_point = 5

        self.assertNotEqual(task.get_points(), false_task_point, 'Task point should be 4')

    def test_already_voted_for_creation_pass(self):
        task = Task.objects.get(id=1)
        developer = Developer.objects.get(id=1)

        self.assertTrue(task.already_voted_for_creation(developer), 'Result should be True')

    def test_already_voted_for_creation_fail(self):
        task = Task.objects.get(id=1)
        developer = Developer.objects.get(id=2)

        self.assertFalse(task.already_voted_for_creation(developer), 'Result should be False')

    def test_already_voted_for_submission_pass(self):
        task = Task.objects.get(id=1)
        developer = Developer.objects.get(id=1)

        self.assertTrue(task.already_voted_for_submission(developer), 'Result should be True')

    def test_already_voted_for_submission_fail(self):
        task = Task.objects.get(id=1)
        developer = Developer.objects.get(id=2)

        self.assertFalse(task.already_voted_for_submission(developer), 'Result should be False')

    def test_get_creation_accept_votes_pass(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=1)

        self.assertEqual(task.get_creation_accept_votes()[0], vote, 'The two votes should be equal')

    def test_get_creation_accept_votes_fail(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=2)

        self.assertNotEqual(task.get_creation_accept_votes()[0], vote, 'The two votes should not be equal')

    def test_get_creation_change_votes_pass(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=2)

        self.assertEqual(task.get_creation_change_votes()[0], vote, 'The two votes should be equal')

    def test_get_creation_change_votes_fail(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=1)

        self.assertNotEqual(task.get_creation_change_votes()[0], vote, 'The two votes should not be equal')

    def test_get_submission_change_votes_pass(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=4)

        self.assertEqual(task.get_submission_change_votes()[0], vote, 'The two votes should be equal')

    def test_get_submission_change_votes_fail(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=3)

        self.assertNotEqual(task.get_submission_change_votes()[0], vote, 'The two votes should not be equal')

    def test_get_submission_accept_votes_pass(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=3)

        self.assertEqual(task.get_submission_accept_votes()[0], vote, 'The two votes should be equal')

    def test_get_submission_accept_votes_fail(self):
        task = Task.objects.get(id=1)
        vote = Vote.objects.get(id=4)

        self.assertNotEqual(task.get_submission_accept_votes()[0], vote, 'The two votes should not be equal')

    def test_apply_self_accept_pass(self):
        task = Task.objects.get(id=2)
        task.apply_self_accept(task.assignee, 1)

        self.assertEqual(
            task.get_creation_accept_votes()[0].voter,
            task.assignee,
            'Voter and task assignee should be the same'
        )

    def test_apply_self_accept_fail(self):
        task = Task.objects.get(id=2)
        task.apply_self_accept(task.assignee, 1)

        self.assertNotEqual(
            task.get_creation_accept_votes()[0].voter,
            Developer.objects.get(id=1),
            'Voter and task assignee should be the same'
        )

    def test_unflag_final_comment_pass(self):
        task = Task.objects.get(id=1)
        task.unflag_final_comment()

        try:
            task.get_final_answer()
            self.assertTrue(False, 'Task should not have a final answer')
        except Comment.DoesNotExist:
            pass

    def test_unflag_final_comment_fail(self):
        task = Task.objects.get(id=1)

        try:
            task.get_final_answer()
            pass
        except Comment.DoesNotExist:
            self.assertTrue(False, 'Task should have a final answer')

    def test_get_final_answer_pass(self):
        task = Task.objects.get(id=1)
        comment_one = Comment.objects.get(id=1)

        try:
            self.assertEqual(task.get_final_answer(), comment_one, 'Task final answer and this comment should be equal')
        except Comment.DoesNotExist:
            self.assertTrue(False, 'Task should have a final answer')

    def test_get_final_answer_fail(self):
        task = Task.objects.get(id=1)
        comment_two = Comment.objects.get(id=2)

        try:
            self.assertNotEqual(task.get_final_answer(), comment_two, 'Task final answer and this comment should not '
                                                                      'be equal')
        except Comment.DoesNotExist:
            pass

    def test_get_differences_from_pass(self):
        task_one = Task.objects.get(id=1)
        task_two = Task.objects.get(id=2)
        differences = task_one.get_differences_from(task_two)

        with self.subTest():
            self.assertEqual(
                differences['assignee'],
                task_one.assignee,
                'Assignee should be equal to ' + task_one.assignee.get_name(),
            )

        with self.subTest():
            self.assertEqual(differences['title'], task_one.title, 'Title should be equal to ' + task_one.title)

        with self.subTest():
            self.assertEqual(
                differences['description'],
                task_one.description,
                'Description should be equal to ' + task_one.description,
            )

    def test_get_differences_from_fail(self):
        task_one = Task.objects.get(id=1)
        differences = task_one.get_differences_from(task_one)

        for key, value in differences.items():
            with self.subTest():
                self.assertEqual(value, '', 'Field ' + key + ' should be empty')

    def test_is_different_from_pass(self):
        task_one = Task.objects.get(id=1)
        task_two = Task.objects.get(id=2)

        self.assertTrue(task_one.is_different_from(task_two), 'Tasks should not be equal')

    def test_is_different_from_fail(self):
        task_one = Task.objects.get(id=1)

        self.assertFalse(task_one.is_different_from(task_one), 'Tasks should be equal')

    def test_can_be_changed_status_by_developer_pass(self):
        task_one = Task.objects.get(id=1)

        self.assertTrue(
            task_one.can_be_changed_status_by(task_one.assignee.user),
            'Task assignee should be able to change status',
        )

    def test_can_be_changed_status_by_developer_fail(self):
        task_one = Task.objects.get(id=1)
        developer_two = Developer.objects.get(id=2)

        self.assertFalse(
            task_one.can_be_changed_status_by(developer_two.user),
            'Non-assignees should not be able to change status',
        )

    def test_can_be_changed_status_by_supervisor_pass(self):
        task_one = Task.objects.get(id=1)

        self.assertTrue(
            task_one.can_be_changed_status_by(task_one.team.supervisor.user),
            'Team\'s supervisor should be able to change status',
        )

    def test_can_be_changed_status_by_supervisor_fail(self):
        task_one = Task.objects.get(id=1)
        supervisor_two = Supervisor.objects.get(id=2)

        self.assertFalse(
            task_one.can_be_changed_status_by(supervisor_two.user),
            'Supervisor should be team\'s supervisor to change status',
        )

    def test_can_be_voted_by_developer_pass(self):
        task_two = Task.objects.get(id=2)
        developer_one = Developer.objects.get(id=1)

        with self.subTest():
            self.assertTrue(
                task_two.can_be_voted_by(task_two.assignee.user),
                'Task assignee should be able to vote',
            )

        with self.subTest():
            self.assertTrue(
                task_two.can_be_voted_by(developer_one.user),
                'Teammates should be able to vote',
            )

    def test_can_be_voted_by_developer_fail(self):
        task_one = Task.objects.get(id=1)
        developer_three = Developer.objects.get(id=3)

        with self.subTest():
            self.assertFalse(
                task_one.can_be_voted_by(developer_three.user),
                'Non-teammates should not be able to vote',
            )

        with self.subTest():
            self.assertFalse(
                task_one.can_be_voted_by(task_one.assignee.user),
                'Developers who voted already should not be able to vote',
            )

        with self.subTest():
            self.assertFalse(
                task_one.can_be_voted_by(task_one.team.supervisor.user),
                'Supervisors should not be able to vote for tasks',
            )

    def test_half_the_team_accepted_pass(self):
        task_three = Task.objects.get(id=3)

        self.assertTrue(
            task_three.half_the_team_accepted(),
            'Result should be true when half the team has accepted',
        )

    def test_half_the_team_accepted_fail(self):
        task_one = Task.objects.get(id=1)

        self.assertFalse(
            task_one.half_the_team_accepted(),
            'Result should be false when half the team has not accepted',
        )

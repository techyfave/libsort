from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Floor, Section, Shelf, Book, Student, BorrowRecord, ShelvingLog, Reminder
from unittest.mock import patch
from django.test import override_settings


class LibraryFlowTests(TestCase):
    def setUp(self):
        floor = Floor.objects.create(name='Ground Floor')
        section = Section.objects.create(name='Social Sciences', floor=floor)
        self.shelf = Shelf.objects.create(code='GF-SS-01', section=section)
        self.other = Shelf.objects.create(code='GF-SS-02', section=section)
        self.book = Book.objects.create(accession='LS-0001', title='Society', author='Demo Author', category='Sociology', shelf=self.shelf)
        self.student = Student.objects.create(student_id='S001', name='Demo Student')
        self.staff = User.objects.create_user('librarian', password='test-password-123', is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def checkout(self):
        return self.client.post('/api/checkout/', {'book_id': self.book.id, 'student_id': self.student.id, 'due_date': str(timezone.localdate()+timedelta(days=14))}, format='json')

    def verify(self, shelf=None):
        return self.client.post('/api/scan-verify/', {'book_code': f'BOOK:{self.book.scan_id}', 'shelf_code': f'SHELF:{(shelf or self.shelf).scan_id}'}, format='json')

    def test_complete_lending_return_and_shelving_cycle(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(self.verify().status_code, 400)
        self.assertEqual(self.client.post(f'/api/loans/{response.data["id"]}/return/').status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual(self.book.state, 'awaiting_shelving')
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(self.verify(self.other).data['result'], 'misplaced')
        self.assertEqual(self.verify().data['result'], 'correct')
        self.book.refresh_from_db()
        self.assertEqual(self.book.state, 'available')
        self.assertEqual(ShelvingLog.objects.count(), 2)
        self.assertEqual(self.checkout().status_code, 201)

    def test_database_rejects_second_active_loan(self):
        self.checkout()
        with self.assertRaises(IntegrityError), transaction.atomic():
            BorrowRecord.objects.create(book=self.book, student=self.student, due_date=timezone.localdate())

    def test_repeated_return_is_rejected(self):
        loan = self.checkout().data['id']
        self.assertEqual(self.client.post(f'/api/loans/{loan}/return/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/loans/{loan}/return/').status_code, 400)

    def test_overdue_is_derived_and_due_today_is_not_overdue(self):
        today = timezone.localdate()
        loan = BorrowRecord.objects.create(book=self.book, student=self.student, borrowed_date=today-timedelta(days=3), due_date=today-timedelta(days=1))
        self.assertEqual(loan.status, 'overdue')
        self.assertEqual(len(self.client.get('/api/loans/?overdue=1').data), 1)
        response = self.client.post(f'/api/loans/{loan.id}/remind/')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Reminder.objects.get().delivery, 'demo_logged')
        loan.due_date = today
        loan.save()
        self.assertEqual(loan.status, 'borrowed')
        self.assertEqual(len(self.client.get('/api/loans/?overdue=1').data), 0)
        self.assertEqual(self.client.post(f'/api/loans/{loan.id}/remind/').status_code, 404)

    def test_public_catalogue_but_private_lending_records(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/books/?q=Society').status_code, 200)
        self.assertEqual(self.client.get('/api/shelves/').status_code, 200)
        for path in ['loans/', 'students/', f'labels/book/{self.book.id}/']:
            self.assertEqual(self.client.get('/api/'+path).status_code, 403)
        self.assertEqual(self.checkout().status_code, 403)
        self.assertEqual(self.verify().status_code, 403)
        user = User.objects.create_user('student', password='test-password-123')
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get('/api/loans/').status_code, 403)

    def test_stable_qr_survives_shelf_code_change(self):
        original = self.client.get(f'/api/labels/book/{self.book.id}/').content
        self.shelf.code = 'RENAMED-01'
        self.shelf.save()
        self.assertEqual(self.verify().data['expected_shelf'], 'RENAMED-01')
        self.assertEqual(self.client.get(f'/api/labels/book/{self.book.id}/').content, original)

    def test_invalid_inputs(self):
        self.assertEqual(self.client.post('/api/checkout/', {}, format='json').status_code, 400)
        self.assertEqual(self.client.get('/api/books/?shelf_id=invalid').status_code, 400)
        self.assertEqual(self.client.post('/api/scan-verify/', {'book_code': 'BOOK:invalid', 'shelf_code': self.shelf.code}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/checkout/', {'book_id':self.book.id,'student_id':self.student.id,'due_date':str(timezone.localdate()-timedelta(days=1))}, format='json').status_code, 400)

    def test_login_and_mutations_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        credentials = {'username':'librarian','password':'test-password-123'}
        self.assertEqual(client.post('/api/login/',credentials,format='json').status_code,403)
        token = client.get('/api/session/').data['csrfToken']
        response = client.post('/api/login/',credentials,format='json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.post('/api/logout/',{},format='json').status_code,403)
        self.assertEqual(client.post('/api/logout/',{},format='json',HTTP_X_CSRFTOKEN=response.json()['csrfToken']).status_code,200)

    def test_search_supports_title_author_accession_category_isbn(self):
        self.book.isbn = '9780000000001'
        self.book.save()
        for query in ['Society','Demo Author','LS-0001','Sociology','9780000000001']:
            self.assertEqual(len(self.client.get('/api/books/', {'q':query}).data),1)

    def test_mismatch_removes_available_status(self):
        self.verify(self.other)
        self.book.refresh_from_db()
        self.assertEqual(self.book.state, 'awaiting_shelving')

    def test_health_and_api_responses_are_not_cached(self):
        self.client.force_authenticate(None)
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_failed_login_is_locked_out(self):
        client = APIClient()
        for _ in range(5):
            response = client.post('/api/login/', {'username':'librarian','password':'incorrect'}, format='json', HTTP_USER_AGENT=f'client-{_}', REMOTE_ADDR=f'192.0.2.{_+1}')
        self.assertEqual(response.status_code, 429)
        response = client.post('/api/login/', {'username':'librarian','password':'test-password-123'}, format='json')
        self.assertEqual(response.status_code, 429)

    @override_settings(CSRF_TRUSTED_ORIGINS=['https://libsort-demo.vercel.app'], SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'), SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_vercel_origin_login_keeps_secure_host_only_cookie(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get('/api/session/', HTTP_X_FORWARDED_PROTO='https').data['csrfToken']
        credentials = {'username':'librarian', 'password':'test-password-123'}
        response = client.post('/api/login/', credentials, format='json', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://libsort-demo.vercel.app', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies['sessionid']['secure'])
        self.assertTrue(response.cookies['sessionid']['httponly'])
        self.assertEqual(response.cookies['sessionid']['domain'], '')
        self.assertEqual(response.cookies['sessionid']['samesite'], 'Lax')

    @override_settings(CSRF_TRUSTED_ORIGINS=['https://libsort-demo.vercel.app'])
    def test_untrusted_frontend_origin_cannot_log_in(self):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get('/api/session/').data['csrfToken']
        response = client.post('/api/login/', {'username':'librarian', 'password':'test-password-123'}, format='json', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='https://untrusted.vercel.app')
        self.assertEqual(response.status_code, 403)


class SeedTests(TestCase):
    def test_deployment_bootstrap_can_recover_existing_admin_credentials(self):
        env = {'DJANGO_SUPERUSER_USERNAME':'client_admin', 'DJANGO_SUPERUSER_EMAIL':'admin@example.com', 'DJANGO_SUPERUSER_PASSWORD':'random-admin-secret-7yJ9zK', 'SEED_DEMO_DATA':'0'}
        with patch.dict('os.environ', env, clear=True):
            call_command('bootstrap_deployment')
        user = User.objects.get(username='client_admin')
        self.assertTrue(user.is_staff and user.is_superuser and user.is_active)
        recovery_env = {**env, 'DJANGO_SUPERUSER_PASSWORD':'new-random-admin-secret-4vX8qP'}
        with patch.dict('os.environ', recovery_env, clear=True):
            call_command('bootstrap_deployment')
        user.refresh_from_db()
        self.assertTrue(user.check_password(recovery_env['DJANGO_SUPERUSER_PASSWORD']))
        self.assertFalse(user.check_password(env['DJANGO_SUPERUSER_PASSWORD']))

    def test_existing_admin_is_unchanged_without_password(self):
        user = User.objects.create_superuser('client_admin', 'admin@example.com', 'original-admin-secret-7yJ9zK')
        with patch.dict('os.environ', {'DJANGO_SUPERUSER_USERNAME':user.username}, clear=True):
            call_command('bootstrap_deployment')
        user.refresh_from_db()
        self.assertTrue(user.check_password('original-admin-secret-7yJ9zK'))

    def test_bootstrap_without_configuration_is_optional(self):
        with patch.dict('os.environ', {}, clear=True):
            call_command('bootstrap_deployment')
        self.assertFalse(User.objects.exists())

    def test_bootstrap_normalizes_dashboard_quotes_and_spaces(self):
        env = {
            'DJANGO_SUPERUSER_USERNAME':'  "quoted_admin"  ',
            'DJANGO_SUPERUSER_EMAIL':" 'admin@example.com' ",
            'DJANGO_SUPERUSER_PASSWORD':'  "quoted-admin-secret-4vX8qP"  ',
        }
        with patch.dict('os.environ', env, clear=True):
            call_command('bootstrap_deployment')
        user = User.objects.get(username='quoted_admin')
        self.assertTrue(user.check_password('quoted-admin-secret-4vX8qP'))

    def test_bootstrap_rejects_incomplete_or_weak_credentials(self):
        for env in [
            {'DJANGO_SUPERUSER_PASSWORD':'secret'},
            {'DJANGO_SUPERUSER_USERNAME':'admin'},
            {'DJANGO_SUPERUSER_USERNAME':'admin', 'DJANGO_SUPERUSER_EMAIL':'admin@example.com', 'DJANGO_SUPERUSER_PASSWORD':'password'},
        ]:
            with self.subTest(env_keys=list(env)), patch.dict('os.environ', env, clear=True):
                with self.assertRaises(CommandError):
                    call_command('bootstrap_deployment')
        self.assertFalse(User.objects.exists())

    def test_bootstrap_promotes_configured_existing_staff(self):
        user = User.objects.create_user('existing_staff', password='original-secret', is_staff=True)
        env = {'DJANGO_SUPERUSER_USERNAME':user.username, 'DJANGO_SUPERUSER_EMAIL':'admin@example.com', 'DJANGO_SUPERUSER_PASSWORD':'new-admin-secret-4vX8qP'}
        with patch.dict('os.environ', env, clear=True):
            call_command('bootstrap_deployment')
        user.refresh_from_db()
        self.assertTrue(user.is_active and user.is_staff and user.is_superuser)
        self.assertTrue(user.check_password(env['DJANGO_SUPERUSER_PASSWORD']))

    def test_seed_is_repeatable(self):
        call_command('seed_demo_data')
        first_counts = (Book.objects.count(), BorrowRecord.objects.count())
        call_command('seed_demo_data')
        self.assertEqual(first_counts, (Book.objects.count(), BorrowRecord.objects.count()))
        self.assertEqual(Floor.objects.count(), 3)
        self.assertEqual(Section.objects.count(), 3)
        self.assertEqual(Shelf.objects.count(), 36)
        self.assertEqual(Book.objects.count(), 108)

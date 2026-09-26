import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone


class Floor(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.name


class Section(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.PROTECT, related_name='sections')
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['floor', 'name'], name='unique_section_on_floor')]

    def __str__(self):
        return f'{self.floor} / {self.name}'


class Shelf(models.Model):
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name='shelves')
    code = models.CharField(max_length=40, unique=True)
    scan_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    directions = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.code


class Book(models.Model):
    class State(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        BORROWED = 'borrowed', 'Borrowed'
        AWAITING = 'awaiting_shelving', 'Awaiting shelving'
    accession = models.CharField(max_length=40, unique=True)
    scan_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=300)
    isbn = models.CharField(max_length=20, blank=True)
    category = models.CharField(max_length=100)
    shelf = models.ForeignKey(Shelf, on_delete=models.PROTECT, related_name='books')
    state = models.CharField(max_length=24, choices=State.choices, default=State.AVAILABLE)

    class Meta:
        ordering = ['title', 'accession']

    def __str__(self):
        return f'{self.accession} — {self.title}'


class Student(models.Model):
    student_id = models.CharField(max_length=40, unique=True, blank=True)
    name = models.CharField(max_length=150)
    contact = models.EmailField(blank=True)  # Acts as the primary email
    phone = models.CharField(max_length=20, blank=True)

    def save(self, *args, **kwargs):
        if not self.student_id:
            from django.utils.crypto import get_random_string
            # Generate an 8-character uppercase alphanumeric ID
            self.student_id = get_random_string(8, allowed_chars='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.student_id} — {self.name}'


class BorrowRecord(models.Model):
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='loans')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='loans')
    borrowed_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['book'], condition=Q(returned_at__isnull=True), name='one_active_loan_per_book'),
            models.CheckConstraint(condition=Q(due_date__gte=F('borrowed_date')), name='due_after_borrow'),
        ]

    @property
    def status(self):
        if self.returned_at:
            return 'returned'
        return 'overdue' if self.due_date < timezone.localdate() else 'borrowed'


class ShelvingLog(models.Model):
    book = models.ForeignKey(Book, on_delete=models.PROTECT)
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scanned_shelf = models.ForeignKey(Shelf, on_delete=models.PROTECT, related_name='+')
    expected_shelf = models.ForeignKey(Shelf, on_delete=models.PROTECT, related_name='+')
    scanned_code = models.CharField(max_length=40)
    expected_code = models.CharField(max_length=40)
    result = models.CharField(max_length=12, choices=[('correct', 'Correct'), ('misplaced', 'Misplaced')])
    timestamp = models.DateTimeField(auto_now_add=True)


class Reminder(models.Model):
    loan = models.ForeignKey(BorrowRecord, on_delete=models.PROTECT, related_name='reminders')
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    delivery = models.CharField(max_length=30, default='demo_logged', editable=False)

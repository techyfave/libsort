from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from core.models import Floor, Section, Shelf, Book, Student, BorrowRecord

class Command(BaseCommand):
    help = 'Create repeatable synthetic demonstration data; does not reset existing records.'

    @transaction.atomic
    def handle(self, *args, **options):
        catalogue = [
            ('Ground Floor', 'Social Sciences', 'GF-SS', 9, ['Introduction to Sociology', 'Principles of Economics', 'Understanding Society', 'Public Administration', 'Research Methods', 'Political Thought']),
            ('First Floor', 'Art', 'FF-ART', 10, ['Foundations of Design', 'African Art and Culture', 'Literature and Society', 'History of Architecture', 'Creative Writing', 'Visual Communication']),
            ('Top Floor', 'Science & Technology', 'TF-ST', 17, ['Database System Concepts', 'Data Structures', 'Foundations of Nursing', 'Applied Mathematics', 'Computer Networks', 'Introduction to Biology']),
        ]
        books = []
        for order, (floor_name, section_name, prefix, count, titles) in enumerate(catalogue):
            floor, _ = Floor.objects.get_or_create(name=floor_name, defaults={'order': order})
            section, _ = Section.objects.get_or_create(floor=floor, name=section_name)
            shelves = [Shelf.objects.get_or_create(code=f'{prefix}-{n:02}', defaults={'section': section, 'directions': f'Shelf {n:02} in the {section_name} section.'})[0] for n in range(1, count + 1)]
            for n in range(36):
                book, created = Book.objects.get_or_create(accession=f'LS-{order * 36 + n + 1:04}', defaults={'title': titles[n % len(titles)], 'author': ['A. Okafor', 'M. Bello', 'T. Adeyemi'][n % 3] + ' (demo)', 'category': section_name, 'shelf': shelves[n % count]})
                if created: books.append(book)
        students = [Student.objects.get_or_create(student_id=f'DEMO-{n:03}', defaults={'name': name, 'contact': f'student{n}@example.com'})[0] for n, name in enumerate(['Ada Okafor', 'Tunde Bello', 'Grace Eze', 'Musa Ibrahim', 'Joy Adeyemi'], 1)]
        today = timezone.localdate()
        for n, book in enumerate(books[:8]):
            BorrowRecord.objects.create(book=book, student=students[n % len(students)], borrowed_date=today-timedelta(days=20), due_date=today+timedelta(days=n-3))
            book.state = Book.State.BORROWED
            book.save(update_fields=['state'])
        for book in books[8:12]:
            BorrowRecord.objects.create(book=book, student=students[0], borrowed_date=today-timedelta(days=5), due_date=today+timedelta(days=9), returned_at=timezone.now())
            book.state = Book.State.AWAITING
            book.save(update_fields=['state'])
        self.stdout.write(self.style.SUCCESS(f'Demo ready: {Book.objects.count()} books, {Shelf.objects.count()} shelves. All catalogue metadata is synthetic.'))

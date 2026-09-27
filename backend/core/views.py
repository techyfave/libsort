import uuid
from io import BytesIO
from urllib.parse import parse_qs, urlencode, urlparse
import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction, IntegrityError
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import Floor, Shelf, Book, Student, BorrowRecord, ShelvingLog, Reminder
from .serializers import BookSerializer, StudentSerializer, LoanSerializer, CheckoutSerializer, ScanSerializer
from .tasks import send_reminder_email

BOOKS = Book.objects.select_related('shelf__section__floor')
LOANS = BorrowRecord.objects.select_related('book__shelf__section__floor', 'student')

def login_locked(request, credentials=None, *args, **kwargs):
    return JsonResponse({'detail': 'Too many failed sign-in attempts. Try again in 15 minutes.'}, status=429)

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    from django.db import connection
    from django.db.utils import DatabaseError
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        return Response({'status': 'unavailable'}, status=503)
    return Response({'status': 'ok'})

@api_view(['GET'])
@permission_classes([AllowAny])
def session(request):
    return Response({'csrfToken': get_token(request), 'staff': request.user.is_authenticated and request.user.is_staff, 'username': request.user.get_username()})

@require_POST
@csrf_protect
def sign_in(request):
    import json
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict): raise ValueError()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'detail': 'Invalid login request.'}, status=400)
    if not isinstance(data.get('username'), str) or not isinstance(data.get('password'), str):
        return JsonResponse({'detail': 'Username and password are required.'}, status=400)
    request.POST = request.POST.copy()
    request.POST['username'] = data['username']
    user = authenticate(request, username=data['username'], password=data['password'])
    if not user or not user.is_staff:
        return JsonResponse({'detail': 'Invalid staff credentials.'}, status=403)
    login(request, user)
    return JsonResponse({'staff': True, 'username': user.username, 'csrfToken': get_token(request)})

@api_view(['POST'])
def sign_out(request):
    logout(request)
    return Response({'detail': 'Signed out.'})

@api_view(['GET'])
@permission_classes([AllowAny])
def books(request):
    qs = BOOKS.all()
    q = request.query_params.get('q', '').strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(isbn__icontains=q) | Q(accession__icontains=q) | Q(category__icontains=q))
    for field in ['state', 'category', 'shelf_id']:
        value = request.query_params.get(field)
        if value:
            if field == 'shelf_id' and not value.isdigit():
                raise ValidationError('Invalid shelf ID.')
            qs = qs.filter(**{field: value})
    return Response(BookSerializer(qs[:200], many=True).data)

@api_view(['GET'])
@permission_classes([AllowAny])
def shelves(request):
    result = []
    for floor in Floor.objects.prefetch_related('sections__shelves'):
        result.append({'id': floor.id, 'name': floor.name, 'sections': [{'id': s.id, 'name': s.name, 'shelves': [{'id': h.id, 'code': h.code, 'scan_id': str(h.scan_id), 'directions': h.directions} for h in s.shelves.all()]} for s in floor.sections.all()]})
    return Response(result)

@api_view(['GET'])
@permission_classes([AllowAny])
def stats(request):
    counts = dict(Book.objects.values_list('state').annotate(total=Count('id')))
    return Response({'total': sum(counts.values()), 'available': counts.get('available', 0), 'borrowed': counts.get('borrowed', 0), 'awaiting_shelving': counts.get('awaiting_shelving', 0), 'shelves': Shelf.objects.count()})

@api_view(['GET'])
def students(request):
    return Response(StudentSerializer(Student.objects.order_by('name'), many=True).data)

@api_view(['GET'])
def loans(request):
    qs = LOANS.filter(returned_at__isnull=True).order_by('due_date')
    if request.query_params.get('overdue') == '1':
        qs = qs.filter(due_date__lt=timezone.localdate())
    return Response(LoanSerializer(qs, many=True).data)

@api_view(['POST'])
def checkout(request):
    data = CheckoutSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    data = data.validated_data
    if data['due_date'] < timezone.localdate():
        raise ValidationError('Due date cannot be in the past.')
    student = get_object_or_404(Student, pk=data['student_id'])
    try:
        with transaction.atomic():
            book = get_object_or_404(Book.objects.select_for_update(), pk=data['book_id'])
            if book.state != Book.State.AVAILABLE:
                raise ValidationError('This book is not available for checkout.')
            loan = BorrowRecord.objects.create(book=book, student=student, due_date=data['due_date'])
            book.state = Book.State.BORROWED
            book.save(update_fields=['state'])
    except IntegrityError:
        raise ValidationError('This book already has an active loan.')
    return Response(LoanSerializer(loan).data, status=201)

@api_view(['POST'])
def return_book(request, pk):
    with transaction.atomic():
        original = get_object_or_404(BorrowRecord, pk=pk)
        book = Book.objects.select_for_update().get(pk=original.book_id)
        loan = BorrowRecord.objects.select_for_update().get(pk=pk)
        if loan.returned_at:
            raise ValidationError('This loan has already been returned.')
        loan.returned_at = timezone.now()
        loan.save(update_fields=['returned_at'])
        book.state = Book.State.AWAITING
        book.save(update_fields=['state'])
    return Response({'detail': 'Return recorded. Verify the shelf to make this book available.', 'book': BookSerializer(BOOKS.get(pk=book.pk)).data})

def resolve_code(model, value, prefix, fallback):
    parsed = urlparse(value)
    if parsed.scheme in ['http', 'https']:
        value = parse_qs(parsed.query).get(prefix.lower(), [value])[0]
    if value.startswith(prefix + ':'):
        try:
            return get_object_or_404(model, scan_id=uuid.UUID(value.split(':', 1)[1]))
        except ValueError:
            raise ValidationError(f'Invalid {prefix} QR code.')
    return get_object_or_404(model, **{fallback: value})

@api_view(['POST'])
def verify(request):
    data = ScanSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    book = resolve_code(Book, data.validated_data['book_code'], 'BOOK', 'accession')
    shelf = resolve_code(Shelf, data.validated_data['shelf_code'], 'SHELF', 'code')
    with transaction.atomic():
        book = BOOKS.select_for_update().get(pk=book.pk)
        if book.state == Book.State.BORROWED:
            raise ValidationError('Record the loan return before shelving this book.')
        correct = shelf.pk == book.shelf_id
        ShelvingLog.objects.create(book=book, staff=request.user, scanned_shelf=shelf, expected_shelf=book.shelf, scanned_code=shelf.code, expected_code=book.shelf.code, result='correct' if correct else 'misplaced')
        # A mismatch means the item is not verified as available on its home shelf.
        book.state = Book.State.AVAILABLE if correct else Book.State.AWAITING
        book.save(update_fields=['state'])
    return Response({'result': 'correct' if correct else 'misplaced', 'expected_shelf': book.shelf.code, 'book': BookSerializer(book).data})

@api_view(['POST'])
def remind(request, pk):
    loan = get_object_or_404(BorrowRecord, pk=pk, returned_at__isnull=True)
    Reminder.objects.create(loan=loan, staff=request.user)
    


    if loan.student.contact:
        # Queue email task asynchronously using Celery
        send_reminder_email.delay(loan.id)
        return Response({'detail': 'Email reminder queued.', 'delivery': 'email_queued'}, status=201)
    return Response({'detail': 'Reminder logged, but student has no email.', 'delivery': 'demo_logged'}, status=201)

@api_view(['GET'])
def label(request, kind, pk):
    if kind not in ['book', 'shelf']:
        raise ValidationError('Unknown label type.')
    obj = get_object_or_404(Book if kind == 'book' else Shelf, pk=pk)
    output = BytesIO()
    code = f'{kind.upper()}:{obj.scan_id}'
    destination = f'{settings.PUBLIC_APP_URL}/?{urlencode({kind: code})}'
    qrcode.make(destination, image_factory=qrcode.image.svg.SvgPathImage).save(output)
    return HttpResponse(output.getvalue(), content_type='image/svg+xml')

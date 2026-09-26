from rest_framework import serializers
from .models import Book, Student, BorrowRecord

class BookSerializer(serializers.ModelSerializer):
    shelf_code = serializers.CharField(source='shelf.code')
    floor = serializers.CharField(source='shelf.section.floor.name')
    section = serializers.CharField(source='shelf.section.name')
    directions = serializers.CharField(source='shelf.directions')
    class Meta:
        model = Book
        fields = ['id', 'accession', 'scan_id', 'title', 'author', 'isbn', 'category', 'state', 'shelf_id', 'shelf_code', 'floor', 'section', 'directions']

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'student_id', 'name', 'contact', 'phone']
        read_only_fields = ['student_id']

class LoanSerializer(serializers.ModelSerializer):
    book = BookSerializer()
    student = StudentSerializer()
    status = serializers.CharField(read_only=True)
    class Meta:
        model = BorrowRecord
        fields = ['id', 'book', 'student', 'borrowed_date', 'due_date', 'returned_at', 'status']

class CheckoutSerializer(serializers.Serializer):
    book_id = serializers.IntegerField(min_value=1)
    student_id = serializers.IntegerField(min_value=1)
    due_date = serializers.DateField()

class ScanSerializer(serializers.Serializer):
    book_code = serializers.CharField(max_length=100)
    shelf_code = serializers.CharField(max_length=100)

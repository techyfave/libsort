from django.contrib import admin
from .models import Floor, Section, Shelf, Book, Student, BorrowRecord, ShelvingLog, Reminder

admin.site.site_header = 'LibSort administration'
admin.site.register([Floor, Section, Student])

@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = ['code', 'section', 'directions']
    readonly_fields = ['scan_id']

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['accession', 'title', 'category', 'shelf', 'state']
    search_fields = ['accession', 'title', 'author', 'isbn']
    list_filter = ['state', 'category']
    readonly_fields = ['scan_id', 'state']

class AuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

admin.site.register([BorrowRecord, ShelvingLog, Reminder], AuditAdmin)

from django.db import migrations


AUTHORS_BY_TITLE = {
    'Introduction to Sociology': 'Amara Okafor',
    'Principles of Economics': 'Musa Bello',
    'Understanding Society': 'Tola Adeyemi',
    'Public Administration': 'Chidi Nwosu',
    'Research Methods': 'Zainab Lawal',
    'Political Thought': 'Kunle Adebayo',
    'Foundations of Design': 'Ifeoma Eze',
    'African Art and Culture': 'Binta Sule',
    'Literature and Society': 'Lara Balogun',
    'History of Architecture': 'Emeka Obi',
    'Creative Writing': 'Sade Williams',
    'Visual Communication': 'Nneka Udo',
    'Database System Concepts': 'David Mensah',
    'Data Structures': 'Amina Yusuf',
    'Foundations of Nursing': 'Grace Ekanem',
    'Applied Mathematics': 'Samuel Okoro',
    'Computer Networks': 'Femi Ajayi',
    'Introduction to Biology': 'Maryam Danjuma',
}


def replace_placeholder_authors(apps, schema_editor):
    Book = apps.get_model('core', 'Book')
    for title, author in AUTHORS_BY_TITLE.items():
        Book.objects.filter(
            title=title,
            author__in=['A. Okafor (demo)', 'M. Bello (demo)', 'T. Adeyemi (demo)'],
        ).update(author=author)


class Migration(migrations.Migration):
    dependencies = [('core', '0001_initial')]
    operations = [migrations.RunPython(replace_placeholder_authors, migrations.RunPython.noop)]
